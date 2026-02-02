from rest_framework import serializers
from alerts.models import Alert, Wishlist, WishlistItem, SavedSearch, PriceAlert


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for alerts/notifications"""
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'alert_type', 'alert_type_display', 'title', 'message',
            'link', 'listing', 'read', 'created'
        ]


class WishlistItemSerializer(serializers.ModelSerializer):
    """Serializer for wishlist items"""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = WishlistItem
        fields = [
            'id', 'search_query', 'category', 'category_name',
            'max_price', 'min_condition', 'notes', 'notify_email', 'created'
        ]


class WishlistSerializer(serializers.ModelSerializer):
    """Serializer for wishlists"""
    items = WishlistItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = [
            'id', 'name', 'description', 'is_public', 'items',
            'item_count', 'created', 'updated'
        ]

    def get_item_count(self, obj):
        return obj.items.count()


class WishlistCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating wishlists"""
    class Meta:
        model = Wishlist
        fields = ['name', 'description', 'is_public']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class SavedSearchSerializer(serializers.ModelSerializer):
    """Serializer for saved searches"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    search_url = serializers.SerializerMethodField()

    class Meta:
        model = SavedSearch
        fields = [
            'id', 'name', 'query', 'category', 'category_name',
            'min_price', 'max_price', 'condition', 'listing_type',
            'grading_company', 'min_grade', 'notify_email', 'notify_push',
            'notify_frequency', 'matches_count', 'is_active',
            'search_url', 'created'
        ]

    def get_search_url(self, obj):
        return obj.get_search_url()


class SavedSearchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating saved searches"""
    class Meta:
        model = SavedSearch
        fields = [
            'name', 'query', 'category', 'min_price', 'max_price',
            'condition', 'listing_type', 'grading_company', 'min_grade',
            'notify_email', 'notify_push', 'notify_frequency'
        ]

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class PriceAlertSerializer(serializers.ModelSerializer):
    """Serializer for price alerts"""
    item_name = serializers.CharField(source='price_guide_item.name', read_only=True)
    item_slug = serializers.CharField(source='price_guide_item.slug', read_only=True)

    class Meta:
        model = PriceAlert
        fields = [
            'id', 'price_guide_item', 'item_name', 'item_slug',
            'target_price', 'grade', 'is_triggered', 'triggered_at',
            'triggered_listing', 'notify_email', 'is_active', 'created'
        ]


class PriceAlertCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating price alerts"""
    class Meta:
        model = PriceAlert
        fields = ['price_guide_item', 'target_price', 'grade', 'notify_email']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
