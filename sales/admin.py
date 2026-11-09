from django.contrib import admin
from .models import Customer, Sale, SaleItem, SaleReturn, SaleReturnItem, SalePayment


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['total']


class SalePaymentInline(admin.TabularInline):
    model = SalePayment
    extra = 0


class SaleReturnItemInline(admin.TabularInline):
    model = SaleReturnItem
    extra = 0
    readonly_fields = ['total']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'phone', 'email', 'balance', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'phone', 'email']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['reference', 'customer', 'warehouse', 'total', 'status', 'payment_status', 'date']
    list_filter = ['status', 'payment_status', 'company', 'currency']
    search_fields = ['reference', 'customer__name']
    readonly_fields = ['total', 'created_at', 'updated_at']
    inlines = [SaleItemInline, SalePaymentInline]


@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    list_display = ['reference', 'sale', 'customer', 'total', 'status', 'reason', 'condition']
    list_filter = ['status', 'reason', 'condition', 'company']
    search_fields = ['reference']
    inlines = [SaleReturnItemInline]
