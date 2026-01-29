from django.contrib import admin
from .models import Collection, CollectionItem


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_public', 'item_count', 'created']
    list_filter = ['is_public', 'created']
    search_fields = ['name', 'user__username']
    raw_id_fields = ['user']


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'collection', 'condition', 'purchase_price', 'current_value', 'created']
    list_filter = ['condition', 'created']
    search_fields = ['name', 'collection__name', 'item__name']
    raw_id_fields = ['collection', 'item', 'listing', 'category']
