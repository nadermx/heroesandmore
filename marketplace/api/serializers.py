from rest_framework import serializers
from django.utils import timezone
from marketplace.models import (
    Listing, Bid, Offer, Order, Review, SavedListing, AuctionEvent, AutoBid,
    AuctionLotSubmission
)
from accounts.api.serializers import PublicProfileSerializer


class ListingImageSerializer(serializers.Serializer):
    """Serialize listing images"""
    url = serializers.SerializerMethodField()
    order = serializers.IntegerField()

    def get_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.url)
        return obj.url


class ListingListSerializer(serializers.ModelSerializer):
    """Compact serializer for listing lists/browse"""
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    seller_is_trusted = serializers.BooleanField(source='seller.profile.is_trusted_seller', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    primary_image = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    bid_count = serializers.SerializerMethodField()
    quantity_available = serializers.SerializerMethodField()
    is_platform_listing = serializers.BooleanField(read_only=True)
    save_count = serializers.SerializerMethodField()
    recent_bids = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'collector_notes', 'price', 'current_price', 'listing_type',
            'condition', 'grading_service', 'grade', 'seller_username',
            'seller_is_trusted',
            'category_name', 'category_slug', 'primary_image',
            'auction_end', 'time_remaining', 'bid_count',
            'shipping_price', 'views', 'created', 'quantity_available',
            'is_platform_listing', 'save_count', 'recent_bids'
        ]

    def get_quantity_available(self, obj):
        return obj.quantity_available

    def get_primary_image(self, obj):
        if obj.image1:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image1.url)
            return obj.image1.url
        return None

    def get_current_price(self, obj):
        return str(obj.get_current_price())

    def get_time_remaining(self, obj):
        remaining = obj.time_remaining()
        if remaining:
            return int(remaining.total_seconds())
        return None

    def get_bid_count(self, obj):
        if obj.listing_type == 'auction':
            return obj.bids.count()
        return 0

    def get_save_count(self, obj):
        return obj.saves.count()

    def get_recent_bids(self, obj):
        if obj.listing_type == 'auction':
            from datetime import timedelta
            one_hour_ago = timezone.now() - timedelta(hours=1)
            return obj.bids.filter(created__gte=one_hour_ago).count()
        return 0


class ListingDetailSerializer(serializers.ModelSerializer):
    """Full serializer for listing detail view"""
    seller = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    current_price = serializers.SerializerMethodField()
    bid_count = serializers.SerializerMethodField()
    high_bidder = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    recent_sales = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    quantity_available = serializers.SerializerMethodField()
    is_platform_listing = serializers.BooleanField(read_only=True)
    watcher_count = serializers.SerializerMethodField()
    recent_bid_count = serializers.SerializerMethodField()
    bid_war_active = serializers.SerializerMethodField()
    comps_range = serializers.SerializerMethodField()
    bid_history = serializers.SerializerMethodField()
    seller_is_trusted = serializers.BooleanField(source='seller.profile.is_trusted_seller', read_only=True)

    class Meta:
        model = Listing
        fields = [
            'id', 'title', 'description', 'collector_notes', 'price', 'current_price',
            'listing_type', 'condition', 'grading_service', 'grade',
            'cert_number', 'is_graded', 'seller', 'category_name',
            'category_slug', 'images', 'allow_offers', 'minimum_offer_percent',
            'quantity', 'quantity_available', 'quantity_sold',
            'shipping_price', 'ships_from', 'auction_end', 'time_remaining',
            'reserve_price', 'no_reserve', 'starting_bid',
            'bid_count', 'high_bidder', 'is_saved', 'recent_sales',
            'views', 'status', 'created', 'is_platform_listing',
            'watcher_count', 'recent_bid_count', 'bid_war_active',
            'comps_range', 'bid_history', 'seller_is_trusted'
        ]

    def get_quantity_available(self, obj):
        return obj.quantity_available

    def get_seller(self, obj):
        return PublicProfileSerializer(
            obj.seller.profile,
            context=self.context
        ).data

    def get_images(self, obj):
        images = []
        for i, img in enumerate(obj.get_images(), 1):
            request = self.context.get('request')
            url = request.build_absolute_uri(img.url) if request else img.url
            images.append({'url': url, 'order': i})
        return images

    def get_current_price(self, obj):
        return str(obj.get_current_price())

    def get_bid_count(self, obj):
        return obj.bids.count() if obj.listing_type == 'auction' else 0

    def get_high_bidder(self, obj):
        if obj.listing_type == 'auction':
            high_bid = obj.bids.order_by('-amount').first()
            if high_bid:
                return high_bid.bidder.username
        return None

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return SavedListing.objects.filter(
                user=request.user, listing=obj
            ).exists()
        return False

    def get_recent_sales(self, obj):
        if obj.price_guide_item:
            sales = obj.price_guide_item.sales.order_by('-sale_date')[:6]
            return [{
                'source': sale.get_source_display(),
                'price': str(sale.sale_price),
                'date': sale.sale_date.isoformat()
            } for sale in sales]
        return []

    def get_time_remaining(self, obj):
        remaining = obj.time_remaining()
        if remaining:
            return int(remaining.total_seconds())
        return None

    def get_watcher_count(self, obj):
        return obj.saves.count()

    def get_recent_bid_count(self, obj):
        if obj.listing_type == 'auction':
            from django.utils import timezone
            from datetime import timedelta
            one_minute_ago = timezone.now() - timedelta(minutes=1)
            return obj.bids.filter(created__gte=one_minute_ago).count()
        return 0

    def get_bid_war_active(self, obj):
        if obj.listing_type == 'auction':
            from django.utils import timezone
            from datetime import timedelta
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            return obj.bids.filter(created__gte=five_minutes_ago).count() >= 3
        return False

    def get_comps_range(self, obj):
        if obj.price_guide_item:
            sales = obj.price_guide_item.sales.order_by('-sale_date')[:6]
            prices = [float(s.sale_price) for s in sales]
            if prices:
                return {'low': str(min(prices)), 'high': str(max(prices))}
        return None

    def get_bid_history(self, obj):
        if obj.listing_type == 'auction':
            bids = obj.bids.select_related('bidder').order_by('-amount')[:10]
            return [{
                'bidder': bid.bidder.username,
                'amount': str(bid.amount),
                'created': bid.created.isoformat()
            } for bid in bids]
        return []


class ListingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating listings"""
    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'collector_notes', 'category', 'condition', 'price',
            'listing_type', 'quantity', 'auction_end', 'reserve_price', 'no_reserve',
            'starting_bid', 'allow_offers', 'minimum_offer_percent',
            'grading_service', 'grade', 'cert_number',
            'shipping_price', 'ships_from',
            'image1', 'image2', 'image3', 'image4', 'image5'
        ]

    def validate(self, data):
        if data.get('listing_type') == 'auction':
            if not data.get('auction_end'):
                raise serializers.ValidationError({
                    'auction_end': 'Auction end time is required for auctions'
                })
            if data['auction_end'] <= timezone.now():
                raise serializers.ValidationError({
                    'auction_end': 'Auction end time must be in the future'
                })
            data['quantity'] = 1
        return data

    def create(self, validated_data):
        validated_data['seller'] = self.context['request'].user
        validated_data['status'] = 'draft'
        instance = super().create(validated_data)
        instance.is_graded = bool(validated_data.get('grading_service') or validated_data.get('grade'))
        update_fields = ['is_graded']
        if instance.listing_type == 'auction':
            instance.starting_bid = instance.price
            update_fields.append('starting_bid')
        instance.save(update_fields=update_fields)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        instance.is_graded = bool(validated_data.get('grading_service') or validated_data.get('grade'))
        update_fields = ['is_graded']
        if instance.listing_type == 'auction':
            instance.starting_bid = instance.price
            update_fields.append('starting_bid')
        instance.save(update_fields=update_fields)
        return instance


class BidSerializer(serializers.ModelSerializer):
    """Serializer for bids"""
    bidder_username = serializers.CharField(source='bidder.username', read_only=True)

    class Meta:
        model = Bid
        fields = ['id', 'amount', 'bidder_username', 'is_winning', 'created']
        read_only_fields = ['bidder_username', 'is_winning', 'created']


class BidCreateSerializer(serializers.Serializer):
    """Serializer for placing a bid"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    max_bid_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Bid amount must be positive")
        return value


class OfferListingSerializer(serializers.ModelSerializer):
    """Compact listing serializer for offers"""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = ['id', 'title', 'price', 'image_url']

    def get_image_url(self, obj):
        if obj.image1:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image1.url)
            return obj.image1.url
        return None


class OfferSerializer(serializers.ModelSerializer):
    """Serializer for offers"""
    listing = OfferListingSerializer(read_only=True)
    buyer_username = serializers.CharField(source='buyer.username', read_only=True)
    is_from_buyer = serializers.SerializerMethodField()
    time_remaining = serializers.CharField(read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id', 'listing', 'amount', 'message',
            'buyer_username', 'status', 'is_from_buyer',
            'counter_amount', 'counter_message', 'time_remaining',
            'expires_at', 'created'
        ]
        read_only_fields = [
            'status', 'counter_amount', 'counter_message',
            'buyer_username', 'expires_at', 'is_from_buyer', 'time_remaining'
        ]

    def get_is_from_buyer(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.buyer == request.user
        return False


class OfferCreateSerializer(serializers.Serializer):
    """Serializer for making an offer"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)


class CounterOfferSerializer(serializers.Serializer):
    """Serializer for counter offers"""
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for orders"""
    listing = ListingListSerializer(read_only=True)
    buyer_username = serializers.CharField(source='buyer.username', read_only=True)
    seller_username = serializers.CharField(source='seller.username', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'listing', 'buyer_username', 'seller_username',
            'quantity', 'item_price', 'shipping_price', 'amount', 'platform_fee',
            'seller_payout', 'status', 'shipping_address',
            'tracking_number', 'tracking_carrier',
            'shipped_at', 'delivered_at', 'created'
        ]


class OrderShipSerializer(serializers.Serializer):
    """Serializer for marking order as shipped"""
    tracking_number = serializers.CharField(max_length=100)
    tracking_carrier = serializers.CharField(max_length=50)


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for reviews"""
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True)
    seller_username = serializers.CharField(source='seller.username', read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'order', 'rating', 'text', 'reviewer_username', 'seller_username', 'created']
        read_only_fields = ['reviewer_username', 'seller_username', 'order']


class ReviewCreateSerializer(serializers.Serializer):
    """Serializer for creating reviews"""
    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class SavedListingSerializer(serializers.ModelSerializer):
    """Serializer for saved listings"""
    listing = ListingListSerializer(read_only=True)

    class Meta:
        model = SavedListing
        fields = ['id', 'listing', 'created']


class AuctionEventSerializer(serializers.ModelSerializer):
    """Serializer for auction events"""
    lot_count = serializers.SerializerMethodField()
    is_live = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()

    class Meta:
        model = AuctionEvent
        fields = [
            'id', 'name', 'slug', 'event_type', 'description',
            'cover_image', 'preview_start', 'bidding_start', 'bidding_end',
            'is_featured', 'is_platform_event', 'cadence', 'status',
            'accepting_submissions', 'submission_deadline',
            'lot_count', 'total_bids', 'total_value',
            'is_live', 'time_remaining'
        ]

    def get_lot_count(self, obj):
        return obj.listings.count()

    def get_is_live(self, obj):
        return obj.is_live()

    def get_time_remaining(self, obj):
        remaining = obj.time_remaining()
        if remaining:
            return int(remaining.total_seconds())
        return None


class AuctionLotSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for auction lot submissions"""
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    listing_image = serializers.SerializerMethodField()
    event_name = serializers.CharField(source='auction_event.name', read_only=True)
    event_slug = serializers.CharField(source='auction_event.slug', read_only=True)

    class Meta:
        model = AuctionLotSubmission
        fields = [
            'id', 'listing_id', 'listing_title', 'listing_image',
            'event_name', 'event_slug', 'status', 'staff_notes',
            'submitted_at', 'reviewed_at'
        ]

    def get_listing_image(self, obj):
        if obj.listing.image1:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.listing.image1.url)
            return obj.listing.image1.url
        return None


class AuctionLotSubmissionCreateSerializer(serializers.Serializer):
    """Serializer for creating a lot submission"""
    listing_id = serializers.IntegerField()


class AutoBidSerializer(serializers.ModelSerializer):
    """Serializer for auto-bids"""
    listing_id = serializers.IntegerField(source='listing.id', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = AutoBid
        fields = ['id', 'listing_id', 'listing_title', 'max_amount', 'is_active', 'created']
        read_only_fields = ['is_active', 'created']


class AutoBidCreateSerializer(serializers.Serializer):
    """Serializer for creating auto-bids"""
    listing_id = serializers.IntegerField()
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_max_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Maximum bid amount must be positive")
        return value


class CheckoutSerializer(serializers.Serializer):
    """Serializer for checkout request"""
    shipping_address = serializers.CharField(max_length=500)
    payment_method_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    quantity = serializers.IntegerField(default=1, min_value=1)


class PaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating payment intent"""
    listing_id = serializers.IntegerField(required=False, allow_null=True)
    offer_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(default=1, min_value=1)

    def validate(self, data):
        if not data.get('listing_id') and not data.get('offer_id'):
            raise serializers.ValidationError("Either listing_id or offer_id is required")
        return data


class PaymentIntentResponseSerializer(serializers.Serializer):
    """Response serializer for payment intent"""
    client_secret = serializers.CharField()
    payment_intent_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class ListingImageUploadSerializer(serializers.Serializer):
    """Serializer for uploading listing images"""
    image = serializers.ImageField()
    position = serializers.IntegerField(min_value=1, max_value=5, required=False, default=1)
