from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
import stripe

from seller_tools.models import SellerSubscription, SubscriptionBillingHistory, BulkImport, BulkImportRow, InventoryItem
from marketplace.models import Order, Listing
from api.permissions import IsVerifiedSeller
from api.pagination import StandardResultsPagination
from .serializers import (
    SellerSubscriptionSerializer, SubscriptionBillingHistorySerializer,
    SubscriptionUpgradeSerializer, InventoryItemSerializer, InventoryItemCreateSerializer,
    BulkImportSerializer, BulkImportCreateSerializer, BulkImportRowSerializer,
    DashboardStatsSerializer
)


class SellerDashboardView(APIView):
    """Get seller dashboard stats"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get stats
        active_listings = Listing.objects.filter(seller=user, status='active').count()
        total_sales = Order.objects.filter(seller=user, status='completed').count()
        total_revenue = Order.objects.filter(
            seller=user, status='completed'
        ).aggregate(total=Sum('seller_payout'))['total'] or 0

        pending_orders = Order.objects.filter(
            seller=user, status='paid'
        ).count()

        avg_rating = user.profile.rating

        # This month stats
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_orders = Order.objects.filter(
            seller=user, status='completed', created__gte=month_start
        )
        this_month_sales = this_month_orders.count()
        this_month_revenue = this_month_orders.aggregate(
            total=Sum('seller_payout')
        )['total'] or 0

        data = {
            'active_listings': active_listings,
            'total_sales': total_sales,
            'total_revenue': str(total_revenue),
            'pending_orders': pending_orders,
            'avg_rating': str(avg_rating),
            'this_month_sales': this_month_sales,
            'this_month_revenue': str(this_month_revenue)
        }

        return Response(data)


class SellerAnalyticsView(APIView):
    """Get detailed seller analytics"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Sales by day
        sales_by_day = Order.objects.filter(
            seller=user,
            status='completed',
            created__gte=start_date
        ).extra(
            select={'day': 'date(created)'}
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('seller_payout')
        ).order_by('day')

        # Top selling items
        top_items = Order.objects.filter(
            seller=user,
            status='completed',
            listing__isnull=False
        ).values(
            'listing__title', 'listing__category__name'
        ).annotate(
            count=Count('id'),
            revenue=Sum('seller_payout')
        ).order_by('-count')[:10]

        return Response({
            'sales_by_day': list(sales_by_day),
            'top_items': list(top_items)
        })


class SubscriptionView(APIView):
    """Get current subscription and manage subscription"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current subscription"""
        subscription, _ = SellerSubscription.objects.get_or_create(
            user=request.user
        )
        serializer = SellerSubscriptionSerializer(subscription)
        return Response(serializer.data)


class SubscriptionUpgradeView(APIView):
    """Upgrade subscription tier"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Upgrade subscription to a new tier.

        Request body:
        - tier: 'basic', 'featured', or 'premium'
        - payment_method_id: Stripe payment method ID (required for initial subscription)
        """
        from marketplace.services.subscription_service import SubscriptionService

        serializer = SubscriptionUpgradeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tier = serializer.validated_data['tier']
        payment_method_id = serializer.validated_data.get('payment_method_id')

        subscription, _ = SellerSubscription.objects.get_or_create(
            user=request.user
        )

        # Check if payment method is needed
        if subscription.tier == 'starter' and not payment_method_id:
            # Check for existing payment method
            if not subscription.default_payment_method:
                return Response(
                    {'error': 'Payment method required for upgrade'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            payment_method_id = subscription.default_payment_method.stripe_payment_method_id

        try:
            if subscription.tier == 'starter':
                # New subscription
                subscription = SubscriptionService.subscribe(
                    request.user, tier, payment_method_id
                )
            else:
                # Tier change
                subscription = SubscriptionService.change_tier(request.user, tier)

            return Response(SellerSubscriptionSerializer(subscription).data)

        except stripe.error.CardError as e:
            return Response(
                {'error': str(e.user_message)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to process subscription'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SubscriptionCancelView(APIView):
    """Cancel subscription"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Cancel subscription at end of billing period"""
        from marketplace.services.subscription_service import SubscriptionService

        try:
            subscription = SubscriptionService.cancel(request.user, at_period_end=True)
            return Response(SellerSubscriptionSerializer(subscription).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SubscriptionReactivateView(APIView):
    """Reactivate a canceled subscription"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Reactivate subscription that was set to cancel"""
        from marketplace.services.subscription_service import SubscriptionService

        try:
            subscription = SubscriptionService.reactivate(request.user)
            return Response(SellerSubscriptionSerializer(subscription).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BillingHistoryView(generics.ListAPIView):
    """Get subscription billing history"""
    serializer_class = SubscriptionBillingHistorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        try:
            subscription = SellerSubscription.objects.get(user=self.request.user)
            return SubscriptionBillingHistory.objects.filter(
                subscription=subscription
            ).order_by('-created')
        except SellerSubscription.DoesNotExist:
            return SubscriptionBillingHistory.objects.none()


class InventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for inventory items"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    search_fields = ['title']
    ordering_fields = ['title', 'created', 'purchase_price', 'target_price']
    ordering = ['-created']

    def get_queryset(self):
        return InventoryItem.objects.filter(
            user=self.request.user
        ).select_related('category')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return InventoryItemCreateSerializer
        return InventoryItemSerializer

    @action(detail=True, methods=['post'])
    def create_listing(self, request, pk=None):
        """Create a listing from inventory item"""
        item = self.get_object()

        if item.is_listed:
            return Response(
                {'error': 'Item is already listed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create listing
        listing = Listing.objects.create(
            seller=request.user,
            title=item.title,
            category=item.category,
            condition=item.condition or 'good',
            grading_service=item.grading_company,
            grade=str(item.grade) if item.grade else '',
            cert_number=item.cert_number,
            price=item.target_price or 0,
            image1=item.image1,
            image2=item.image2,
            image3=item.image3,
            description='',
            price_guide_item=item.price_guide_item,
            status='draft'
        )

        item.is_listed = True
        item.listing = listing
        item.save()

        from marketplace.api.serializers import ListingDetailSerializer
        return Response(
            ListingDetailSerializer(listing, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class BulkImportViewSet(viewsets.ModelViewSet):
    """ViewSet for bulk imports"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return BulkImport.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return BulkImportCreateSerializer
        return BulkImportSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file = serializer.validated_data['file']
        file_type = file.name.split('.')[-1].lower()

        if file_type not in ['csv', 'xlsx']:
            return Response(
                {'error': 'Invalid file type. Must be CSV or XLSX'},
                status=status.HTTP_400_BAD_REQUEST
            )

        bulk_import = BulkImport.objects.create(
            user=request.user,
            file=file,
            file_name=file.name,
            file_type=file_type,
            auto_publish=serializer.validated_data.get('auto_publish', False),
            default_category_id=serializer.validated_data.get('default_category')
        )

        # TODO: Trigger async task to process import
        # from seller_tools.tasks import process_bulk_import
        # process_bulk_import.delay(bulk_import.id)

        return Response(
            BulkImportSerializer(bulk_import).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'])
    def rows(self, request, pk=None):
        """Get rows for a bulk import"""
        bulk_import = self.get_object()
        rows = bulk_import.rows.all()
        serializer = BulkImportRowSerializer(rows, many=True)
        return Response(serializer.data)


class SellerOrdersView(generics.ListAPIView):
    """Get orders to fulfill (seller view)"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        from marketplace.models import Order
        return Order.objects.filter(
            seller=self.request.user
        ).exclude(
            status__in=['completed', 'cancelled', 'refunded']
        ).select_related('listing', 'buyer')

    def get_serializer_class(self):
        from marketplace.api.serializers import OrderSerializer
        return OrderSerializer


class SellerSalesHistoryView(generics.ListAPIView):
    """Get sales history"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        from marketplace.models import Order
        return Order.objects.filter(
            seller=self.request.user,
            status='completed'
        ).select_related('listing', 'buyer')

    def get_serializer_class(self):
        from marketplace.api.serializers import OrderSerializer
        return OrderSerializer
