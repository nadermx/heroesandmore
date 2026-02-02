from rest_framework import serializers
from items.models import Category, Item


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for categories"""
    children = serializers.SerializerMethodField()
    listing_count = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'parent', 'description', 'icon',
            'image_url', 'order', 'children', 'listing_count'
        ]

    def get_children(self, obj):
        # Only include children for top-level categories
        if obj.parent is None:
            children = obj.children.filter(is_active=True)
            return CategorySerializer(children, many=True, context=self.context).data
        return []

    def get_listing_count(self, obj):
        return obj.listings.filter(status='active').count()

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class CategoryListSerializer(serializers.ModelSerializer):
    """Simpler serializer for category lists"""
    parent_name = serializers.CharField(source='parent.name', read_only=True, allow_null=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'parent_name', 'icon']


class ItemSerializer(serializers.ModelSerializer):
    """Serializer for items"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = [
            'id', 'name', 'slug', 'category', 'category_name',
            'description', 'year', 'manufacturer', 'primary_image',
            'attributes', 'estimated_value', 'last_sale_price'
        ]

    def get_primary_image(self, obj):
        if obj.images and len(obj.images) > 0:
            request = self.context.get('request')
            img_url = obj.images[0]
            if request and not img_url.startswith('http'):
                return request.build_absolute_uri(img_url)
            return img_url
        return None


class SearchResultSerializer(serializers.Serializer):
    """Serializer for search results"""
    type = serializers.CharField()  # 'listing', 'item', 'price_guide'
    id = serializers.IntegerField()
    title = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    image_url = serializers.CharField(allow_null=True)
    url = serializers.CharField()


class AutocompleteSerializer(serializers.Serializer):
    """Serializer for autocomplete suggestions"""
    text = serializers.CharField()
    type = serializers.CharField()
    url = serializers.CharField()
