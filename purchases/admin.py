from django.contrib import admin
from .models import Supplier, Purchase, PurchaseItem, PurchaseReturn, PurchaseReturnItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    readonly_fields = ['total']


class PurchaseReturnItemInline(admin.TabularInline):
    model = PurchaseReturnItem
    extra = 0
    readonly_fields = ['total']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'contact_person', 'phone', 'balance', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'contact_person', 'phone', 'email']


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['reference', 'supplier', 'warehouse', 'total', 'status', 'payment_status', 'order_date']
    list_filter = ['status', 'payment_status', 'company', 'currency']
    search_fields = ['reference', 'supplier__name']
    readonly_fields = ['total', 'created_at', 'updated_at']
    inlines = [PurchaseItemInline]


@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ['reference', 'purchase', 'supplier', 'total', 'status', 'reason']
    list_filter = ['status', 'reason', 'company']
    search_fields = ['reference']
    inlines = [PurchaseReturnItemInline]
