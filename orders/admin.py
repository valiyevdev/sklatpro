from django.contrib import admin
from .models import Order, OrderItem, OrderPayment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['total']


class OrderPaymentInline(admin.TabularInline):
    model = OrderPayment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['reference', 'customer', 'warehouse', 'total', 'status', 'priority', 'payment_status', 'date']
    list_filter = ['status', 'payment_status', 'priority', 'company']
    search_fields = ['reference', 'customer__name']
    readonly_fields = ['total', 'created_at', 'updated_at']
    inlines = [OrderItemInline, OrderPaymentInline]
