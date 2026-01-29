from django.contrib import admin
from .models import Listing, Bid, Offer, Order, Review, SavedListing, AuctionEvent


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
    list_display = ['id', 'listing', 'buyer', 'seller', 'amount', 'status', 'created']
    list_filter = ['status', 'created']
    search_fields = ['listing__title', 'buyer__username', 'seller__username']
    readonly_fields = ['created', 'updated']
    raw_id_fields = ['listing', 'buyer', 'seller']


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
