from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils import timezone
from .models import (
    Listing, Bid, Offer, Order, Review, SavedListing, AuctionEvent,
    PaymentMethod, StripeEvent, Refund, AuctionLotSubmission
)


class PlatformLotInline(admin.TabularInline):
    model = Listing
    fk_name = 'auction_event'
    fields = ['title', 'category', 'starting_bid', 'price', 'condition', 'lot_number', 'status', 'image1']
    raw_id_fields = ['category']
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')


class AuctionLotSubmissionInline(admin.TabularInline):
    model = AuctionLotSubmission
    fields = ['seller', 'listing', 'status', 'staff_notes', 'submitted_at', 'reviewed_at']
    readonly_fields = ['submitted_at', 'reviewed_at']
    raw_id_fields = ['seller', 'listing']
    extra = 0


@admin.register(AuctionEvent)
class AuctionEventAdmin(admin.ModelAdmin):
    list_display = ['name', 'event_type', 'is_platform_event', 'cadence', 'status', 'accepting_submissions', 'bidding_start', 'bidding_end', 'total_lots', 'is_featured']
    list_filter = ['is_platform_event', 'event_type', 'cadence', 'status', 'accepting_submissions', 'is_featured', 'bidding_start']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['total_lots', 'total_bids', 'total_value', 'created', 'cover_image_preview']
    raw_id_fields = ['created_by']
    inlines = [PlatformLotInline, AuctionLotSubmissionInline]
    actions = ['activate_platform_event']
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'event_type', 'description')
        }),
        ('Timing', {
            'fields': ('preview_start', 'bidding_start', 'bidding_end')
        }),
        ('Cover Image & Focal Point', {
            'fields': ('cover_image', 'cover_image_preview', 'cover_image_position_x', 'cover_image_position_y'),
            'description': 'Upload a cover image, then click on the preview to set the focal point. The crosshair shows where the image will be centered when cropped.'
        }),
        ('Display', {
            'fields': ('is_featured', 'status')
        }),
        ('Platform Auction', {
            'fields': ('is_platform_event', 'cadence', 'accepting_submissions', 'submission_deadline'),
            'classes': ('collapse',)
        }),
        ('Stats', {
            'fields': ('total_lots', 'total_bids', 'total_value', 'created'),
            'classes': ('collapse',)
        }),
        ('Created By', {
            'fields': ('created_by',),
        }),
    )

    def cover_image_preview(self, obj):
        if obj.cover_image:
            return format_html('''
                <div id="focal-point-container" style="position: relative; display: inline-block; max-width: 600px; cursor: crosshair; border: 2px solid #ccc; border-radius: 4px; overflow: hidden;">
                    <img id="focal-point-image" src="{}" style="max-width: 600px; height: auto; display: block; object-fit: cover; object-position: {}% {}%;" />
                    <div id="focal-point-crosshair" style="position: absolute; width: 30px; height: 30px; border: 2px solid #E63946; border-radius: 50%; transform: translate(-50%, -50%); pointer-events: none; left: {}%; top: {}%; box-shadow: 0 0 0 2px rgba(255,255,255,0.8), inset 0 0 0 1px rgba(230,57,70,0.5);">
                        <div style="position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: #E63946;"></div>
                        <div style="position: absolute; top: 50%; left: 0; right: 0; height: 1px; background: #E63946;"></div>
                    </div>
                </div>
                <div style="margin-top: 8px; color: #666; font-size: 12px;">
                    Click on the image to set the focal point. Current: <strong id="focal-point-display">{}%, {}%</strong>
                </div>
                <div id="focal-point-crop-preview" style="margin-top: 12px; width: 300px; height: 120px; overflow: hidden; border: 1px solid #ddd; border-radius: 4px;">
                    <img src="{}" style="width: 100%; height: 100%; object-fit: cover; object-position: {}% {}%;" id="focal-point-crop-img" />
                </div>
                <div style="color: #999; font-size: 11px; margin-top: 4px;">Crop preview (how it appears on homepage)</div>
                <script>
                (function() {{
                    var container = document.getElementById('focal-point-container');
                    var crosshair = document.getElementById('focal-point-crosshair');
                    var display = document.getElementById('focal-point-display');
                    var cropImg = document.getElementById('focal-point-crop-img');
                    var xInput = document.getElementById('id_cover_image_position_x');
                    var yInput = document.getElementById('id_cover_image_position_y');

                    container.addEventListener('click', function(e) {{
                        var rect = container.getBoundingClientRect();
                        var x = Math.round(((e.clientX - rect.left) / rect.width) * 100);
                        var y = Math.round(((e.clientY - rect.top) / rect.height) * 100);
                        x = Math.max(0, Math.min(100, x));
                        y = Math.max(0, Math.min(100, y));
                        crosshair.style.left = x + '%';
                        crosshair.style.top = y + '%';
                        display.textContent = x + '%, ' + y + '%';
                        cropImg.style.objectPosition = x + '% ' + y + '%';
                        if (xInput) xInput.value = x;
                        if (yInput) yInput.value = y;
                    }});
                }})();
                </script>
            ''',
                obj.cover_image.url,
                obj.cover_image_position_x, obj.cover_image_position_y,
                obj.cover_image_position_x, obj.cover_image_position_y,
                obj.cover_image_position_x, obj.cover_image_position_y,
                obj.cover_image.url,
                obj.cover_image_position_x, obj.cover_image_position_y,
            )
        return "No cover image uploaded yet."
    cover_image_preview.short_description = "Focal Point Preview"

    def save_model(self, request, obj, form, change):
        """Override to trigger notifications when submissions open."""
        if change:
            old_obj = AuctionEvent.objects.get(pk=obj.pk)
            was_accepting = old_obj.accepting_submissions
        else:
            was_accepting = False

        super().save_model(request, obj, form, change)

        # Trigger notification when accepting_submissions changes to True
        if obj.accepting_submissions and not was_accepting and obj.is_platform_event:
            from alerts.tasks import notify_trusted_sellers_new_event
            notify_trusted_sellers_new_event.delay(obj.id)
            self.message_user(request, 'Trusted sellers will be notified about this event.')

    def activate_platform_event(self, request, queryset):
        """Activate all draft listings in selected platform events and sync auction_end times."""
        from django.contrib.auth.models import User

        for event in queryset.filter(is_platform_event=True):
            lots = event.listings.filter(status='draft')
            count = lots.update(
                status='active',
                auction_end=event.bidding_end,
                listing_type='auction',
            )
            # Update cached total_lots
            event.total_lots = event.listings.filter(status='active').count()
            event.status = 'live'
            event.save(update_fields=['total_lots', 'status'])
            self.message_user(request, f'{event.name}: activated {count} lots, event set to live.')
    activate_platform_event.short_description = "Activate platform event (set lots live, sync end times)"


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
        ('Videos', {
            'fields': ('video1', 'video2', 'video3', 'video_url'),
            'classes': ('collapse',)
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
    actions = ['process_full_refund', 'retry_transfer', 'mark_shipped']

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

    def mark_shipped(self, request, queryset):
        """Bulk mark orders as shipped (useful for platform orders)"""
        from django.utils import timezone
        count = queryset.filter(status='paid').update(
            status='shipped',
            shipped_at=timezone.now(),
        )
        self.message_user(request, f"Marked {count} order(s) as shipped.")
    mark_shipped.short_description = "Mark as shipped"


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


@admin.register(AuctionLotSubmission)
class AuctionLotSubmissionAdmin(admin.ModelAdmin):
    list_display = ['listing', 'seller', 'auction_event', 'status', 'submitted_at', 'reviewed_at']
    list_filter = ['status', 'auction_event', 'submitted_at']
    search_fields = ['listing__title', 'seller__username', 'auction_event__name']
    readonly_fields = ['submitted_at']
    raw_id_fields = ['seller', 'listing', 'auction_event', 'reviewed_by']
    actions = ['approve_submissions', 'reject_submissions']

    def approve_submissions(self, request, queryset):
        """Approve selected submissions and link listings to the auction event."""
        for submission in queryset.filter(status='pending'):
            listing = submission.listing
            event = submission.auction_event
            # Assign lot number (next available)
            max_lot = event.listings.aggregate(max_lot=models.Max('lot_number'))['max_lot'] or 0
            listing.auction_event = event
            listing.lot_number = max_lot + 1
            listing.save(update_fields=['auction_event', 'lot_number'])
            submission.status = 'approved'
            submission.reviewed_at = timezone.now()
            submission.reviewed_by = request.user
            submission.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
        self.message_user(request, f'Approved {queryset.filter(status="approved").count()} submission(s).')
    approve_submissions.short_description = "Approve selected submissions"

    def reject_submissions(self, request, queryset):
        """Reject selected submissions."""
        count = queryset.filter(status='pending').update(
            status='rejected',
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f'Rejected {count} submission(s).')
    reject_submissions.short_description = "Reject selected submissions"
