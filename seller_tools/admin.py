from django.contrib import admin
from .models import SellerSubscription, BulkImport, BulkImportRow, InventoryItem


@admin.register(SellerSubscription)
class SellerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'tier', 'max_active_listings', 'commission_rate', 'is_active', 'current_period_end']
    list_filter = ['tier', 'is_active']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created', 'updated']


class BulkImportRowInline(admin.TabularInline):
    model = BulkImportRow
    extra = 0
    readonly_fields = ['row_number', 'status', 'error_message', 'listing']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BulkImport)
class BulkImportAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'file_name', 'status', 'total_rows', 'success_count', 'error_count', 'created']
    list_filter = ['status', 'created']
    search_fields = ['user__username', 'file_name']
    readonly_fields = ['total_rows', 'processed_rows', 'success_count', 'error_count', 'errors',
                       'started_at', 'completed_at', 'created']
    inlines = [BulkImportRowInline]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'category', 'condition', 'purchase_price', 'target_price', 'is_listed', 'created']
    list_filter = ['category', 'is_listed', 'created']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created', 'updated']
