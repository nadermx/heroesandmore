from django.contrib import admin
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_seller_verified', 'rating', 'is_public', 'created']
    list_filter = ['is_seller_verified', 'is_public', 'created']
    search_fields = ['user__username', 'user__email', 'location']
    readonly_fields = ['rating', 'rating_count', 'created', 'updated']
