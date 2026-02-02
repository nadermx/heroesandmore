from rest_framework import serializers
from seller_tools.models import SellerSubscription, SubscriptionBillingHistory, BulkImport, BulkImportRow, InventoryItem


class SellerSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for seller subscriptions"""
    tier_info = serializers.SerializerMethodField()
    remaining_listings = serializers.SerializerMethodField()
    can_create_listing = serializers.SerializerMethodField()
    default_payment_method_display = serializers.SerializerMethodField()

    class Meta:
        model = SellerSubscription
        fields = [
            'id', 'tier', 'tier_info', 'max_active_listings',
            'commission_rate', 'featured_slots', 'is_active',
            'subscription_status', 'current_period_start', 'current_period_end',
            'cancel_at_period_end', 'remaining_listings', 'can_create_listing',
            'default_payment_method_display', 'failed_payment_attempts',
            'grace_period_end'
        ]

    def get_tier_info(self, obj):
        return obj.get_tier_info()

    def get_remaining_listings(self, obj):
        return obj.get_remaining_listings()

    def get_can_create_listing(self, obj):
        return obj.can_create_listing()

    def get_default_payment_method_display(self, obj):
        if obj.default_payment_method:
            pm = obj.default_payment_method
            return f"{pm.card_brand.title()} ****{pm.card_last4}"
        return None


class SubscriptionBillingHistorySerializer(serializers.ModelSerializer):
    """Serializer for subscription billing history"""
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = SubscriptionBillingHistory
        fields = [
            'id', 'transaction_type', 'transaction_type_display',
            'amount', 'tier', 'status', 'status_display',
            'stripe_payment_intent_id', 'period_start', 'period_end',
            'failure_reason', 'created'
        ]


class SubscriptionUpgradeSerializer(serializers.Serializer):
    """Serializer for subscription upgrade request"""
    tier = serializers.ChoiceField(choices=['basic', 'featured', 'premium'])
    payment_method_id = serializers.CharField(required=False)

    def validate_tier(self, value):
        if value not in SellerSubscription.TIER_DETAILS:
            raise serializers.ValidationError(f"Invalid tier: {value}")
        return value


class InventoryItemSerializer(serializers.ModelSerializer):
    """Serializer for inventory items"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    estimated_profit = serializers.SerializerMethodField()
    image1_url = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = [
            'id', 'title', 'category', 'category_name', 'condition',
            'grading_company', 'grade', 'cert_number',
            'purchase_price', 'purchase_date', 'purchase_source',
            'target_price', 'minimum_price', 'estimated_profit',
            'image1', 'image1_url', 'image2', 'image3',
            'price_guide_item', 'is_listed', 'listing', 'notes',
            'created', 'updated'
        ]
        read_only_fields = ['is_listed', 'listing']

    def get_estimated_profit(self, obj):
        profit = obj.get_estimated_profit()
        return str(profit) if profit else None

    def get_image1_url(self, obj):
        if obj.image1:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image1.url)
            return obj.image1.url
        return None


class InventoryItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating inventory items"""
    class Meta:
        model = InventoryItem
        fields = [
            'title', 'category', 'condition', 'grading_company', 'grade',
            'cert_number', 'purchase_price', 'purchase_date', 'purchase_source',
            'target_price', 'minimum_price', 'image1', 'image2', 'image3',
            'price_guide_item', 'notes'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BulkImportSerializer(serializers.ModelSerializer):
    """Serializer for bulk imports"""
    progress_percent = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = BulkImport
        fields = [
            'id', 'file_name', 'file_type', 'status', 'status_display',
            'total_rows', 'processed_rows', 'success_count', 'error_count',
            'progress_percent', 'errors', 'auto_publish',
            'started_at', 'completed_at', 'created'
        ]

    def get_progress_percent(self, obj):
        return obj.get_progress_percent()


class BulkImportCreateSerializer(serializers.Serializer):
    """Serializer for creating bulk imports"""
    file = serializers.FileField()
    auto_publish = serializers.BooleanField(default=False)
    default_category = serializers.IntegerField(required=False, allow_null=True)


class BulkImportRowSerializer(serializers.ModelSerializer):
    """Serializer for bulk import rows"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = BulkImportRow
        fields = ['id', 'row_number', 'data', 'status', 'status_display', 'error_message', 'listing']


class DashboardStatsSerializer(serializers.Serializer):
    """Serializer for seller dashboard stats"""
    active_listings = serializers.IntegerField()
    total_sales = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_orders = serializers.IntegerField()
    avg_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    this_month_sales = serializers.IntegerField()
    this_month_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
