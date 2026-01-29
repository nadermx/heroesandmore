from django.contrib import admin
from .models import Listing, Bid, Offer, Order, Review, SavedListing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'seller', 'category', 'price', 'listing_type', 'status', 'views', 'created']
    list_filter = ['status', 'listing_type', 'condition', 'category', 'created']
    search_fields = ['title', 'description', 'seller__username']
    readonly_fields = ['views', 'created', 'updated']
    raw_id_fields = ['seller', 'item', 'category']


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ['listing', 'bidder', 'amount', 'created']
    list_filter = ['created']
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
