from django.contrib import admin
from .models import Address, ShippingProfile, ShippingLabel, ShippingRate


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'city', 'state', 'country', 'is_verified', 'is_default']
    list_filter = ['is_verified', 'is_default', 'country']
    search_fields = ['name', 'street1', 'city', 'state', 'zip_code', 'user__username']
    raw_id_fields = ['user']


@admin.register(ShippingProfile)
class ShippingProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'profile_type', 'weight_oz', 'length_in', 'width_in', 'height_in', 'is_active', 'sort_order']
    list_filter = ['profile_type', 'is_active']
    list_editable = ['sort_order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ShippingLabel)
class ShippingLabelAdmin(admin.ModelAdmin):
    list_display = ['order', 'carrier', 'service', 'rate', 'tracking_number', 'is_voided', 'created']
    list_filter = ['carrier', 'is_voided']
    search_fields = ['tracking_number', 'easypost_shipment_id']
    raw_id_fields = ['order']


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = ['listing', 'carrier', 'service', 'rate', 'est_delivery_days', 'expires_at']
    list_filter = ['carrier']
    raw_id_fields = ['listing', 'to_address']
