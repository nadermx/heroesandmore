from rest_framework import serializers
from pricing.models import PriceGuideItem, GradePrice, SaleRecord


class GradePriceSerializer(serializers.ModelSerializer):
    """Serializer for grade prices"""
    grading_company_display = serializers.CharField(
        source='get_grading_company_display', read_only=True
    )

    class Meta:
        model = GradePrice
        fields = [
            'id', 'grading_company', 'grading_company_display', 'grade',
            'avg_price', 'low_price', 'high_price', 'median_price',
            'num_sales', 'last_sale_price', 'last_sale_date',
            'price_change_30d', 'updated'
        ]


class SaleRecordSerializer(serializers.ModelSerializer):
    """Serializer for sale records"""
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = SaleRecord
        fields = [
            'id', 'sale_price', 'sale_date', 'source', 'source_display',
            'source_url', 'grading_company', 'grade', 'cert_number'
        ]


class PriceGuideItemListSerializer(serializers.ModelSerializer):
    """Compact serializer for price guide listing"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PriceGuideItem
        fields = [
            'id', 'name', 'slug', 'year', 'set_name', 'card_number',
            'variant', 'category_name', 'category_slug', 'image_url',
            'total_sales', 'avg_sale_price', 'price_trend'
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class PriceGuideItemDetailSerializer(serializers.ModelSerializer):
    """Full serializer for price guide item detail"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    image_url = serializers.SerializerMethodField()
    grade_prices = GradePriceSerializer(many=True, read_only=True)

    class Meta:
        model = PriceGuideItem
        fields = [
            'id', 'name', 'slug', 'year', 'set_name', 'card_number',
            'variant', 'publisher', 'volume', 'issue_number',
            'description', 'image_url', 'image_source_url', 'category_name', 'category_slug',
            'total_sales', 'avg_sale_price', 'last_sale_date', 'price_trend',
            'grade_prices', 'created', 'updated'
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class PriceHistorySerializer(serializers.Serializer):
    """Serializer for price history data (for charts)"""
    month = serializers.DateField()
    avg_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()
