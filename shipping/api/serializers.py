from rest_framework import serializers
from shipping.models import Address, ShippingProfile, ShippingLabel, ShippingRate


class AddressSerializer(serializers.ModelSerializer):
    formatted = serializers.CharField(read_only=True)

    class Meta:
        model = Address
        fields = [
            'id', 'name', 'company', 'street1', 'street2',
            'city', 'state', 'zip_code', 'country', 'phone',
            'is_verified', 'is_default', 'formatted',
        ]
        read_only_fields = ['id', 'is_verified', 'formatted']


class ShippingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingProfile
        fields = [
            'id', 'name', 'slug', 'profile_type',
            'weight_oz', 'length_in', 'width_in', 'height_in',
            'predefined_package', 'customs_description', 'hs_tariff_number',
        ]


class ShippingLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingLabel
        fields = [
            'id', 'order', 'carrier', 'service', 'rate',
            'tracking_number', 'label_url', 'label_format',
            'is_voided', 'created',
        ]
        read_only_fields = fields


class ShippingRateSerializer(serializers.Serializer):
    """Serializer for rate quote results (not a model serializer)."""
    rate_id = serializers.CharField()
    shipment_id = serializers.CharField()
    carrier = serializers.CharField()
    service = serializers.CharField()
    rate = serializers.DecimalField(max_digits=8, decimal_places=2)
    days = serializers.IntegerField(allow_null=True)


class ValidateAddressSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    street1 = serializers.CharField(max_length=200)
    street2 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zip = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=2, default='US')


class GetRatesSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField()
    name = serializers.CharField(max_length=200)
    street1 = serializers.CharField(max_length=200)
    street2 = serializers.CharField(max_length=200, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    zip = serializers.CharField(max_length=20)
    country = serializers.CharField(max_length=2, default='US')


class BuyLabelSerializer(serializers.Serializer):
    shipment_id = serializers.CharField()
    rate_id = serializers.CharField()


class TrackingEventSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    datetime = serializers.CharField()
    city = serializers.CharField(allow_blank=True)
    state = serializers.CharField(allow_blank=True)


class TrackingSerializer(serializers.Serializer):
    status = serializers.CharField()
    est_delivery_date = serializers.CharField(allow_null=True)
    events = TrackingEventSerializer(many=True)
