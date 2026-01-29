from django.contrib import admin
from .models import ScanResult, ScanSession


@admin.register(ScanResult)
class ScanResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'identified_item', 'confidence', 'created']
    list_filter = ['status', 'created']
    search_fields = ['user__username', 'identified_item__name']
    readonly_fields = ['extracted_data', 'created', 'processed_at']


@admin.register(ScanSession)
class ScanSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'name', 'total_scans', 'successful_scans', 'failed_scans', 'created']
    list_filter = ['created']
    search_fields = ['user__username', 'name']
    readonly_fields = ['created', 'completed_at']
