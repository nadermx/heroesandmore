from rest_framework import serializers
from scanner.models import ScanResult, ScanSession


class ScanResultSerializer(serializers.ModelSerializer):
    """Serializer for scan results"""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    identified_item_name = serializers.CharField(
        source='identified_item.name', read_only=True, allow_null=True
    )
    suggested_title = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ScanResult
        fields = [
            'id', 'image', 'image_url', 'status', 'status_display',
            'identified_item', 'identified_item_name', 'confidence',
            'extracted_data', 'suggested_title', 'error_message',
            'converted_to_listing', 'added_to_collection',
            'created', 'processed_at'
        ]

    def get_suggested_title(self, obj):
        return obj.get_suggested_title()

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ScanUploadSerializer(serializers.Serializer):
    """Serializer for uploading scan image"""
    image = serializers.ImageField()


class ScanSessionSerializer(serializers.ModelSerializer):
    """Serializer for scan sessions"""
    class Meta:
        model = ScanSession
        fields = [
            'id', 'name', 'total_scans', 'successful_scans',
            'failed_scans', 'created', 'completed_at'
        ]


class ScanSessionCreateSerializer(serializers.Serializer):
    """Serializer for creating scan sessions"""
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class CreateFromScanSerializer(serializers.Serializer):
    """Serializer for creating listing/collection item from scan"""
    # For listing
    title = serializers.CharField(max_length=200, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    category = serializers.IntegerField(required=False)

    # For collection
    collection_id = serializers.IntegerField(required=False)
    purchase_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
