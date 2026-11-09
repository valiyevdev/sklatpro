from django.contrib import admin
from .models import Product, Category, Brand, Unit, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'sort_order', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['name']
    ordering = ['sort_order', 'name']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    ordering = ['name']


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['name', 'symbol', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'symbol']
    ordering = ['name']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['name', 'sku', 'barcode', 'price', 'purchase_price', 'quantity', 'is_active']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'brand', 'quantity', 'purchase_price', 'price', 'status', 'created_at']
    list_filter = ['status', 'category', 'brand', 'created_at']
    search_fields = ['name', 'sku', 'barcode']
    readonly_fields = ['sku', 'barcode', 'created_at', 'updated_at']
    ordering = ['-created_at']
    list_per_page = 25
    inlines = [ProductVariantInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'sku', 'barcode', 'description', 'status', 'image')
        }),
        ('Classification', {
            'fields': ('category', 'category_fk', 'brand', 'unit')
        }),
        ('Pricing', {
            'fields': ('purchase_price', 'price')
        }),
        ('Stock', {
            'fields': ('quantity', 'min_stock', 'max_stock')
        }),
        ('Dimensions', {
            'fields': ('weight', 'length', 'width', 'height'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('shelf', 'rack', 'section')
        }),
        ('Batch & Expiry', {
            'fields': ('batch_number', 'expiration_date')
        }),
        ('Other', {
            'fields': ('supplier', 'qr_code', 'notes', 'company')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
