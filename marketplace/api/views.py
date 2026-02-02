from rest_framework import generics, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal

from marketplace.models import (
    Listing, Bid, Offer, Order, Review, SavedListing, AuctionEvent
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
    SavedListingSerializer, AuctionEventSerializer
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
                listing.auction_end = timezone.now() + timezone.timedelta(
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
            expires_at=timezone.now() + timezone.timedelta(hours=48)
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
        from django.conf import settings
        platform_fee = offer.amount * Decimal(settings.PLATFORM_FEE_PERCENT) / 100

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

        serializer = CounterOfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        offer.status = 'countered'
        offer.counter_amount = serializer.validated_data['amount']
        offer.counter_message = serializer.validated_data.get('message', '')
        offer.countered_at = timezone.now()
        offer.expires_at = timezone.now() + timezone.timedelta(hours=48)
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
        one_hour = timezone.now() + timezone.timedelta(hours=1)
        return Listing.objects.filter(
            status='active',
            listing_type='auction',
            auction_end__lte=one_hour,
            auction_end__gt=timezone.now()
        ).order_by('auction_end')
