from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Listing, Bid, Offer, Order, Review, SavedListing, AuctionEvent,
    PaymentMethod, StripeEvent, Refund
)


@admin.register(AuctionEvent)
class AuctionEventAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'status', 'bidding_start', 'bidding_end', 'total_lots', 'is_featured']
    list_filter = ['event_type', 'status', 'is_featured', 'bidding_start']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['total_lots', 'total_bids', 'total_value', 'created']
    raw_id_fields = ['created_by']


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'seller', 'category', 'price', 'listing_type', 'status', 'views', 'created']
    list_filter = ['status', 'listing_type', 'condition', 'category', 'is_graded', 'auction_event', 'created']
    search_fields = ['title', 'description', 'seller__username', 'cert_number']
    readonly_fields = ['views', 'times_extended', 'auto_identified', 'identification_confidence', 'created', 'updated']
    raw_id_fields = ['seller', 'item', 'category', 'price_guide_item', 'auction_event']
    fieldsets = (
        (None, {
            'fields': ('seller', 'category', 'item', 'title', 'description', 'condition')
        }),
        ('Grading', {
            'fields': ('is_graded', 'grading_service', 'grade', 'cert_number', 'price_guide_item'),
            'classes': ('collapse',)
        }),
        ('Pricing', {
            'fields': ('price', 'listing_type', 'allow_offers', 'minimum_offer_percent')
        }),
        ('Auction Settings', {
            'fields': ('auction_end', 'starting_bid', 'reserve_price', 'no_reserve',
                      'use_extended_bidding', 'extended_bidding_minutes', 'times_extended',
                      'auction_event', 'lot_number'),
            'classes': ('collapse',)
        }),
        ('Images', {
            'fields': ('image1', 'image2', 'image3', 'image4', 'image5')
        }),
        ('Shipping', {
            'fields': ('shipping_price', 'ships_from')
        }),
        ('Status', {
            'fields': ('status', 'views', 'auto_identified', 'identification_confidence', 'created', 'updated')
        }),
    )


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ['listing', 'bidder', 'amount', 'is_auto_bid', 'max_bid_amount', 'triggered_extension', 'is_winning', 'created']
    list_filter = ['is_auto_bid', 'triggered_extension', 'is_winning', 'created']
    search_fields = ['listing__title', 'bidder__username']
    raw_id_fields = ['listing', 'bidder']


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['listing', 'buyer', 'amount', 'status', 'created']
    list_filter = ['status', 'created']
    search_fields = ['listing__title', 'buyer__username']
    raw_id_fields = ['listing', 'buyer']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'listing', 'buyer', 'seller', 'amount', 'status', 'stripe_payment_status', 'created']
    list_filter = ['status', 'stripe_payment_status', 'created']
    search_fields = ['listing__title', 'buyer__username', 'seller__username', 'stripe_payment_intent']
    readonly_fields = [
        'stripe_payment_intent', 'stripe_payment_status', 'stripe_transfer_id',
        'stripe_transfer_status', 'platform_fee', 'stripe_fee', 'seller_payout',
        'refund_amount', 'refund_status', 'stripe_refund_id',
        'created', 'updated', 'paid_at'
    ]
    raw_id_fields = ['listing', 'buyer', 'seller']
    fieldsets = (
        (None, {
            'fields': ('listing', 'buyer', 'seller', 'status')
        }),
        ('Pricing', {
            'fields': ('item_price', 'shipping_price', 'amount', 'platform_fee', 'stripe_fee', 'seller_payout')
        }),
        ('Payment', {
            'fields': ('stripe_payment_intent', 'stripe_payment_status', 'paid_at'),
        }),
        ('Transfer', {
            'fields': ('stripe_transfer_id', 'stripe_transfer_status'),
            'classes': ('collapse',)
        }),
        ('Refund', {
            'fields': ('refund_amount', 'refund_status', 'stripe_refund_id'),
            'classes': ('collapse',)
        }),
        ('Shipping', {
            'fields': ('shipping_address', 'tracking_number', 'tracking_carrier', 'shipped_at', 'delivered_at')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    actions = ['process_full_refund', 'retry_transfer']

    def process_full_refund(self, request, queryset):
        """Process full refund for selected orders"""
        from marketplace.services.stripe_service import StripeService
        for order in queryset:
            if order.stripe_payment_intent and order.status == 'paid':
                try:
                    StripeService.create_refund(order)
                    self.message_user(request, f"Refund processed for Order #{order.id}")
                except Exception as e:
                    self.message_user(request, f"Refund failed for Order #{order.id}: {e}", level='error')
            else:
                self.message_user(request, f"Cannot refund Order #{order.id} - not in paid status", level='warning')
    process_full_refund.short_description = "Process full refund"

    def retry_transfer(self, request, queryset):
        """Retry transfer to seller for orders without transfer"""
        from marketplace.services.connect_service import ConnectService
        for order in queryset:
            if order.status == 'paid' and not order.stripe_transfer_id:
                try:
                    ConnectService.create_transfer(order)
                    self.message_user(request, f"Transfer created for Order #{order.id}")
                except Exception as e:
                    self.message_user(request, f"Transfer failed for Order #{order.id}: {e}", level='error')
    retry_transfer.short_description = "Retry seller transfer"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['order', 'reviewer', 'seller', 'rating', 'created']
    list_filter = ['rating', 'created']
    search_fields = ['reviewer__username', 'seller__username', 'text']
    raw_id_fields = ['order', 'reviewer', 'seller']


@admin.register(SavedListing)
class SavedListingAdmin(admin.ModelAdmin):
    list_display = ['user', 'listing', 'created']
    list_filter = ['created']
    raw_id_fields = ['user', 'listing']


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['user', 'card_display', 'is_default', 'created']
    list_filter = ['card_brand', 'is_default', 'created']
    search_fields = ['user__username', 'stripe_payment_method_id', 'card_last4']
    readonly_fields = ['stripe_payment_method_id', 'card_brand', 'card_last4', 'card_exp_month', 'card_exp_year', 'created']
    raw_id_fields = ['user']

    def card_display(self, obj):
        return f"{obj.card_brand.title()} ****{obj.card_last4}"
    card_display.short_description = 'Card'


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ['stripe_event_id_short', 'event_type', 'processed', 'processed_at', 'has_error', 'created']
    list_filter = ['event_type', 'processed', 'created']
    search_fields = ['stripe_event_id', 'event_type', 'error_message']
    readonly_fields = ['stripe_event_id', 'event_type', 'processed', 'processed_at', 'error_message', 'raw_data', 'created']
    ordering = ['-created']

    def stripe_event_id_short(self, obj):
        return obj.stripe_event_id[:25] + '...'
    stripe_event_id_short.short_description = 'Event ID'

    def has_error(self, obj):
        if obj.error_message:
            return format_html('<span style="color: red;">Yes</span>')
        return format_html('<span style="color: green;">No</span>')
    has_error.short_description = 'Error'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_link', 'amount', 'reason', 'status', 'created_by', 'created']
    list_filter = ['status', 'reason', 'created']
    search_fields = ['order__id', 'stripe_refund_id', 'notes']
    readonly_fields = ['stripe_refund_id', 'created']
    raw_id_fields = ['order', 'created_by']

    def order_link(self, obj):
        return format_html(
            '<a href="/admin/marketplace/order/{}/change/">Order #{}</a>',
            obj.order.id, obj.order.id
        )
    order_link.short_description = 'Order'
