from django.contrib import admin
from .models import PriceGuideItem, GradePrice, SaleRecord


class GradePriceInline(admin.TabularInline):
    model = GradePrice
    extra = 0


@admin.register(PriceGuideItem)
class PriceGuideItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'year', 'set_name', 'avg_sale_price', 'total_sales', 'price_trend', 'has_image']
    list_filter = ['category', 'price_trend', 'year', 'image_source']
    search_fields = ['name', 'set_name', 'card_number', 'publisher']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [GradePriceInline]
    readonly_fields = ['total_sales', 'avg_sale_price', 'last_sale_date', 'price_trend', 'image_source_url', 'image_source', 'created', 'updated']

    @admin.display(boolean=True, description='Image')
    def has_image(self, obj):
        return bool(obj.image)


@admin.register(GradePrice)
class GradePriceAdmin(admin.ModelAdmin):
    list_display = ['price_guide_item', 'grading_company', 'grade', 'avg_price', 'num_sales', 'last_sale_date']
    list_filter = ['grading_company', 'grade']
    search_fields = ['price_guide_item__name']
    readonly_fields = ['updated']


@admin.register(SaleRecord)
class SaleRecordAdmin(admin.ModelAdmin):
    list_display = ['price_guide_item', 'sale_price', 'sale_date', 'source', 'grading_company', 'grade']
    list_filter = ['source', 'grading_company', 'sale_date']
    search_fields = ['price_guide_item__name', 'cert_number']
    date_hierarchy = 'sale_date'
    readonly_fields = ['created']
