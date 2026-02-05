from rest_framework import generics, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from decimal import Decimal

from marketplace.models import (
    Listing, Bid, Offer, Order, Review, SavedListing, AuctionEvent, AutoBid
)
from accounts.models import RecentlyViewed
from api.permissions import IsOwnerOrReadOnly, IsBuyerOrSeller
from api.pagination import StandardResultsPagination
from .serializers import (
    ListingListSerializer, ListingDetailSerializer, ListingCreateSerializer,
    BidSerializer, BidCreateSerializer,
    OfferSerializer, OfferCreateSerializer, CounterOfferSerializer,
    OrderSerializer, OrderShipSerializer,
    ReviewSerializer, ReviewCreateSerializer,
    SavedListingSerializer, AuctionEventSerializer,
    AutoBidSerializer, AutoBidCreateSerializer,
    CheckoutSerializer, PaymentIntentSerializer, PaymentIntentResponseSerializer,
    ListingImageUploadSerializer
)
from .filters import ListingFilter, OrderFilter


class ListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listings.
    Supports list, create, retrieve, update, destroy.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    filterset_class = ListingFilter
    search_fields = ['title', 'description']
    ordering_fields = ['price', 'created', 'views', 'auction_end']
    ordering = ['-created']

    def get_queryset(self):
        queryset = Listing.objects.select_related('seller', 'category')

        # For list view, only show active listings
        if self.action == 'list':
            queryset = queryset.filter(status='active')

        # For detail/update/delete, check ownership
        elif self.action in ['update', 'partial_update', 'destroy']:
            if self.request.user.is_authenticated:
                queryset = queryset.filter(seller=self.request.user)

        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ListingListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ListingCreateSerializer
        return ListingDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Record view
        instance.views += 1
        instance.save(update_fields=['views'])
        # Track recently viewed
        if request.user.is_authenticated:
            RecentlyViewed.record_view(request.user, instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def publish(self, request, pk=None):
        """Publish a draft listing"""
        listing = get_object_or_404(Listing, pk=pk, seller=request.user)
        if listing.status != 'draft':
            return Response(
                {'error': 'Only draft listings can be published'},
                status=status.HTTP_400_BAD_REQUEST
            )
        listing.status = 'active'
        listing.save()
        return Response({'status': 'published'})

    @action(detail=True, methods=['get', 'post', 'delete'], permission_classes=[IsAuthenticated])
    def save(self, request, pk=None):
        """Save/unsave a listing"""
        listing = get_object_or_404(Listing, pk=pk, status='active')

        if request.method == 'GET':
            is_saved = SavedListing.objects.filter(
                user=request.user, listing=listing
            ).exists()
            return Response({'is_saved': is_saved})

        elif request.method == 'POST':
            SavedListing.objects.get_or_create(user=request.user, listing=listing)
            return Response({'status': 'saved'})

        elif request.method == 'DELETE':
            SavedListing.objects.filter(user=request.user, listing=listing).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def bid(self, request, pk=None):
        """Place a bid on an auction listing"""
        listing = get_object_or_404(Listing, pk=pk, status='active', listing_type='auction')

        # Check if auction is still active
        if listing.is_auction_ended():
            return Response(
                {'error': 'Auction has ended'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cannot bid on own listing
        if listing.seller == request.user:
            return Response(
                {'error': 'Cannot bid on your own listing'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = BidCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        current_price = listing.get_current_price()
        min_bid = current_price + Decimal('1.00')  # Minimum increment

        if amount < min_bid:
            return Response(
                {'error': f'Bid must be at least ${min_bid}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create bid
        bid = Bid.objects.create(
            listing=listing,
            bidder=request.user,
            amount=amount,
            max_bid_amount=serializer.validated_data.get('max_bid_amount')
        )

        # Handle extended bidding (anti-sniping)
        if listing.use_extended_bidding and listing.auction_end:
            time_left = listing.auction_end - timezone.now()
            if time_left.total_seconds() < listing.extended_bidding_minutes * 60:
                listing.auction_end = timezone.now() + timedelta(
                    minutes=listing.extended_bidding_minutes
                )
                listing.times_extended += 1
                listing.save()
                bid.triggered_extension = True
                bid.save()

        return Response(BidSerializer(bid).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def bids(self, request, pk=None):
        """Get bid history for a listing"""
        listing = get_object_or_404(Listing, pk=pk)
        bids = listing.bids.all()[:50]
        serializer = BidSerializer(bids, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def offer(self, request, pk=None):
        """Make an offer on a listing"""
        listing = get_object_or_404(Listing, pk=pk, status='active', allow_offers=True)

        if listing.seller == request.user:
            return Response(
                {'error': 'Cannot make offer on your own listing'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = OfferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        min_offer = listing.price * Decimal(listing.minimum_offer_percent) / 100

        if amount < min_offer:
            return Response(
                {'error': f'Offer must be at least ${min_offer:.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create offer with 48 hour expiry
        offer = Offer.objects.create(
            listing=listing,
            buyer=request.user,
            amount=amount,
            message=serializer.validated_data.get('message', ''),
            expires_at=timezone.now() + timedelta(hours=48)
        )

        return Response(OfferSerializer(offer).data, status=status.HTTP_201_CREATED)


class SavedListingsView(generics.ListAPIView):
    """Get user's saved listings"""
    serializer_class = SavedListingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedListing.objects.filter(
            user=self.request.user
        ).select_related('listing', 'listing__seller', 'listing__category')


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for offers"""
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Show offers where user is buyer or seller
        return Offer.objects.filter(
            Q(buyer=user) | Q(listing__seller=user)
        ).select_related('listing', 'buyer')

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept an offer (seller only)"""
        offer = get_object_or_404(
            Offer, pk=pk, listing__seller=request.user, status='pending'
        )

        if offer.is_expired():
            return Response(
                {'error': 'Offer has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        offer.status = 'accepted'
        offer.responded_at = timezone.now()
        offer.save()

        # Create order
        listing = offer.listing
        from marketplace.services.stripe_service import StripeService
        commission_rate = StripeService.get_seller_commission_rate(listing.seller)
        platform_fee = offer.amount * commission_rate

        Order.objects.create(
            listing=listing,
            buyer=offer.buyer,
            seller=listing.seller,
            item_price=offer.amount,
            shipping_price=listing.shipping_price,
            amount=offer.amount + listing.shipping_price,
            platform_fee=platform_fee,
            seller_payout=offer.amount - platform_fee,
            shipping_address='',  # To be filled during checkout
            status='pending'
        )

        listing.status = 'sold'
        listing.save()

        return Response({'status': 'accepted'})

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        """Decline an offer (seller only)"""
        offer = get_object_or_404(
            Offer, pk=pk, listing__seller=request.user, status='pending'
        )
        offer.status = 'declined'
        offer.responded_at = timezone.now()
        offer.save()
        return Response({'status': 'declined'})

    @action(detail=True, methods=['post'])
    def counter(self, request, pk=None):
        """Counter an offer (seller only)"""
        offer = get_object_or_404(
            Offer, pk=pk, listing__seller=request.user, status='pending'
        )

        if offer.is_expired():
            return Response(
                {'error': 'Offer has expired'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CounterOfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        offer.status = 'countered'
        offer.counter_amount = serializer.validated_data['amount']
        offer.counter_message = serializer.validated_data.get('message', '')
        offer.countered_at = timezone.now()
        offer.expires_at = timezone.now() + timedelta(hours=48)
        offer.save()

        return Response(OfferSerializer(offer).data)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for orders"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter

    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(
            Q(buyer=user) | Q(seller=user)
        ).select_related('listing', 'buyer', 'seller')

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """Mark order as shipped (seller only)"""
        order = get_object_or_404(Order, pk=pk, seller=request.user, status='paid')

        serializer = OrderShipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order.tracking_number = serializer.validated_data['tracking_number']
        order.tracking_carrier = serializer.validated_data['tracking_carrier']
        order.status = 'shipped'
        order.shipped_at = timezone.now()
        order.save()

        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def received(self, request, pk=None):
        """Confirm order received (buyer only)"""
        order = get_object_or_404(Order, pk=pk, buyer=request.user, status='shipped')

        order.status = 'delivered'
        order.delivered_at = timezone.now()
        order.save()

        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Leave review for order (buyer only)"""
        order = get_object_or_404(
            Order, pk=pk, buyer=request.user, status__in=['delivered', 'completed']
        )

        # Check if review already exists
        if hasattr(order, 'review'):
            return Response(
                {'error': 'Review already exists for this order'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = Review.objects.create(
            order=order,
            reviewer=request.user,
            seller=order.seller,
            rating=serializer.validated_data['rating'],
            text=serializer.validated_data.get('text', '')
        )

        # Mark order as completed
        order.status = 'completed'
        order.save()

        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class AuctionEventListView(generics.ListAPIView):
    """List auction events"""
    serializer_class = AuctionEventSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return AuctionEvent.objects.filter(
            status__in=['preview', 'live']
        ).order_by('bidding_start')


class AuctionEventDetailView(generics.RetrieveAPIView):
    """Get auction event detail"""
    serializer_class = AuctionEventSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        return AuctionEvent.objects.all()


class AuctionEventLotsView(generics.ListAPIView):
    """Get lots for an auction event"""
    serializer_class = ListingListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        slug = self.kwargs['slug']
        event = get_object_or_404(AuctionEvent, slug=slug)
        return event.listings.filter(status='active').order_by('lot_number')


class EndingSoonView(generics.ListAPIView):
    """Get auctions ending soon (within 1 hour)"""
    serializer_class = ListingListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        one_hour = timezone.now() + timedelta(hours=1)
        return Listing.objects.filter(
            status='active',
            listing_type='auction',
            auction_end__lte=one_hour,
            auction_end__gt=timezone.now()
        ).order_by('auction_end')


class ListingImageUploadView(views.APIView):
    """Upload image to a listing"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, seller=request.user)

        serializer = ListingImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image = serializer.validated_data['image']
        position = serializer.validated_data.get('position', 1)

        # Find first empty slot or use specified position
        image_fields = ['image1', 'image2', 'image3', 'image4', 'image5']

        if position:
            field_name = f'image{position}'
            setattr(listing, field_name, image)
        else:
            # Find first empty slot
            for field_name in image_fields:
                if not getattr(listing, field_name):
                    setattr(listing, field_name, image)
                    break
            else:
                return Response(
                    {'error': 'All image slots are full'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        listing.save()

        return Response({
            'message': 'Image uploaded successfully',
            'position': position or image_fields.index(field_name) + 1
        }, status=status.HTTP_201_CREATED)


class ListingImageDeleteView(views.APIView):
    """Delete image from a listing"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, image_id):
        listing = get_object_or_404(Listing, pk=pk, seller=request.user)

        # image_id is 1-5
        if image_id < 1 or image_id > 5:
            return Response(
                {'error': 'Invalid image position'},
                status=status.HTTP_400_BAD_REQUEST
            )

        field_name = f'image{image_id}'
        image_field = getattr(listing, field_name)

        if not image_field:
            return Response(
                {'error': 'No image at this position'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Delete the image file
        image_field.delete(save=False)
        setattr(listing, field_name, None)
        listing.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutView(views.APIView):
    """Create an order and initiate checkout"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk)

        if listing.seller == request.user:
            return Response(
                {'error': 'Cannot purchase your own listing'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if listing.status != 'active':
            order = Order.objects.filter(
                listing=listing,
                buyer=request.user,
                status__in=['pending', 'payment_failed']
            ).first()
            if not order:
                return Response(
                    {'error': 'Listing is no longer available'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            if Order.objects.filter(
                listing=listing,
                status__in=['pending', 'payment_failed']
            ).exclude(buyer=request.user).exists():
                return Response(
                    {'error': 'Listing is currently in another checkout'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate fees
            from marketplace.services.stripe_service import StripeService
            platform_fee_percent = StripeService.get_seller_commission_rate(listing.seller)
            price = listing.get_current_price()
            platform_fee = price * platform_fee_percent
            total = price + listing.shipping_price

            # Create pending order
            order, _ = Order.objects.get_or_create(
                listing=listing,
                buyer=request.user,
                status='pending',
                defaults={
                    'seller': listing.seller,
                    'item_price': price,
                    'shipping_price': listing.shipping_price,
                    'amount': total,
                    'platform_fee': platform_fee,
                    'seller_payout': price - platform_fee,
                    'shipping_address': serializer.validated_data['shipping_address'],
                }
            )

        from marketplace.services.stripe_service import StripeService
        if order.stripe_payment_intent:
            intent = StripeService.retrieve_payment_intent(order.stripe_payment_intent)
            if intent.status in ['canceled', 'requires_payment_method']:
                intent = StripeService.create_payment_intent(order)
        else:
            intent = StripeService.create_payment_intent(order)

        return Response({
            'order': OrderSerializer(order).data,
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
        }, status=status.HTTP_201_CREATED)


class PaymentIntentView(views.APIView):
    """Create a Stripe PaymentIntent for an order"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        listing_id = serializer.validated_data.get('listing_id')
        offer_id = serializer.validated_data.get('offer_id')

        if listing_id:
            listing = get_object_or_404(Listing, pk=listing_id)
            if listing.status != 'active':
                order = Order.objects.filter(
                    listing=listing,
                    buyer=request.user,
                    status__in=['pending', 'payment_failed']
                ).first()
                if not order:
                    return Response(
                        {'error': 'Listing is no longer available'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                if Order.objects.filter(
                    listing=listing,
                    status__in=['pending', 'payment_failed']
                ).exclude(buyer=request.user).exists():
                    return Response(
                        {'error': 'Listing is currently in another checkout'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                from marketplace.services.stripe_service import StripeService
                platform_fee_percent = StripeService.get_seller_commission_rate(listing.seller)
                price = listing.get_current_price()
                platform_fee = price * platform_fee_percent
                total = price + listing.shipping_price
                order, _ = Order.objects.get_or_create(
                    listing=listing,
                    buyer=request.user,
                    status='pending',
                    defaults={
                        'seller': listing.seller,
                        'item_price': price,
                        'shipping_price': listing.shipping_price,
                        'amount': total,
                        'platform_fee': platform_fee,
                        'seller_payout': price - platform_fee,
                        'shipping_address': '',
                    }
                )
        elif offer_id:
            offer = get_object_or_404(
                Offer, pk=offer_id, buyer=request.user, status='accepted'
            )
            listing = offer.listing
            order = Order.objects.filter(
                listing=listing,
                buyer=request.user,
                status__in=['pending', 'payment_failed']
            ).first()
            if not order:
                return Response(
                    {'error': 'Order not found for this offer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            return Response(
                {'error': 'listing_id or offer_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Stripe PaymentIntent
        try:
            from marketplace.services.stripe_service import StripeService
            if order.stripe_payment_intent:
                intent = StripeService.retrieve_payment_intent(order.stripe_payment_intent)
                if intent.status in ['canceled', 'requires_payment_method']:
                    intent = StripeService.create_payment_intent(order)
            else:
                intent = StripeService.create_payment_intent(order)
            return Response({
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'order_id': order.id,
                'amount': str(order.amount),
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PaymentConfirmView(views.APIView):
    """Confirm a payment and complete the order"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_intent_id = request.data.get('payment_intent_id')
        if not payment_intent_id:
            return Response(
                {'error': 'payment_intent_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find the order by payment intent
        order = get_object_or_404(
            Order, stripe_payment_intent=payment_intent_id, buyer=request.user
        )

        # Verify payment status with Stripe
        try:
            from marketplace.services.stripe_service import StripeService
            intent = StripeService.retrieve_payment_intent(payment_intent_id)

            if intent.status == 'succeeded':
                order.status = 'paid'
                order.stripe_payment_status = 'succeeded'
                order.paid_at = timezone.now()
                order.save(update_fields=['status', 'stripe_payment_status', 'paid_at', 'updated'])
                if order.listing and order.listing.status != 'sold':
                    order.listing.status = 'sold'
                    order.listing.save(update_fields=['status'])
                return Response(OrderSerializer(order).data)
            else:
                return Response(
                    {'error': f'Payment status: {intent.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class AutoBidListView(views.APIView):
    """List and create auto-bids"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's active auto-bids"""
        auto_bids = AutoBid.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('listing')
        serializer = AutoBidSerializer(auto_bids, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create or update an auto-bid"""
        serializer = AutoBidCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        listing_id = serializer.validated_data['listing_id']
        max_amount = serializer.validated_data['max_amount']

        listing = get_object_or_404(
            Listing, pk=listing_id, status='active', listing_type='auction'
        )

        if listing.seller == request.user:
            return Response(
                {'error': 'Cannot auto-bid on your own listing'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check auction is still active
        if listing.is_auction_ended():
            return Response(
                {'error': 'Auction has ended'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Must be higher than current price
        current_price = listing.get_current_price()
        if max_amount <= current_price:
            return Response(
                {'error': f'Max amount must be higher than current price ${current_price}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create or update auto-bid
        auto_bid, created = AutoBid.objects.update_or_create(
            user=request.user,
            listing=listing,
            defaults={'max_amount': max_amount, 'is_active': True}
        )

        return Response(
            AutoBidSerializer(auto_bid).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class AutoBidDeleteView(views.APIView):
    """Delete/cancel an auto-bid"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        auto_bid = get_object_or_404(AutoBid, pk=pk, user=request.user)
        auto_bid.deactivate()
        return Response(status=status.HTTP_204_NO_CONTENT)
