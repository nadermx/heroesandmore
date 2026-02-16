from django.contrib import admin
from .models import Wishlist, WishlistItem, Alert, SavedSearch, NewsletterSubscriber


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_public', 'created']
    list_filter = ['is_public', 'created']
    search_fields = ['name', 'user__username']
    raw_id_fields = ['user']


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['search_query', 'wishlist', 'category', 'max_price', 'notify_email', 'created']
    list_filter = ['notify_email', 'category', 'created']
    search_fields = ['search_query', 'wishlist__name']
    raw_id_fields = ['wishlist', 'category']


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'alert_type', 'title', 'read', 'emailed', 'created']
    list_filter = ['alert_type', 'read', 'emailed', 'created']
    search_fields = ['user__username', 'title', 'message']
    raw_id_fields = ['user', 'listing']


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'query', 'category', 'notify_email', 'created']
    list_filter = ['notify_email', 'category', 'created']
    search_fields = ['name', 'user__username', 'query']
    raw_id_fields = ['user', 'category']


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_verified', 'is_active', 'frequency', 'subscribed_at', 'verified_at']
    list_filter = ['is_verified', 'is_active', 'frequency', 'subscribed_at']
    search_fields = ['email', 'user__username']
    readonly_fields = ['verification_token', 'unsubscribe_token', 'subscribed_at', 'verified_at', 'unsubscribed_at']
    raw_id_fields = ['user']
    filter_horizontal = ['categories']
