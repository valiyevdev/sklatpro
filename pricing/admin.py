from django.contrib import admin
from .models import (
    PriceList, PriceListEntry, CustomerSpecificPrice,
    Promotion, Coupon, CouponUsage, PriceHistory,
)


class PriceListEntryInline(admin.TabularInline):
    model = PriceListEntry
    extra = 0


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'currency', 'status', 'priority', 'channel', 'is_default', 'company')
    list_filter = ('status', 'currency', 'channel', 'company')
    search_fields = ('name', 'code')
    inlines = [PriceListEntryInline]


@admin.register(PriceListEntry)
class PriceListEntryAdmin(admin.ModelAdmin):
    list_display = ('price_list', 'product', 'price', 'min_quantity', 'max_quantity', 'is_active')
    list_filter = ('price_list', 'is_active')
    search_fields = ('product__name',)


@admin.register(CustomerSpecificPrice)
class CustomerSpecificPriceAdmin(admin.ModelAdmin):
    list_display = ('customer', 'product', 'price', 'currency', 'priority', 'is_active', 'company')
    list_filter = ('is_active', 'currency', 'company')
    search_fields = ('customer__name', 'product__name')


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'discount_type', 'discount_value', 'status', 'priority', 'company')
    list_filter = ('status', 'discount_type', 'company')
    search_fields = ('name', 'code')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'discount_type', 'discount_value', 'is_active', 'current_uses', 'company')
    list_filter = ('is_active', 'discount_type', 'company')
    search_fields = ('code', 'name')


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'customer', 'discount_amount', 'used_at')
    list_filter = ('coupon',)


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'old_price', 'new_price', 'change_type', 'changed_by', 'changed_at')
    list_filter = ('change_type', 'company')
    search_fields = ('product__name',)
