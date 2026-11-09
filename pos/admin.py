from django.contrib import admin
from .models import POSTerminal, CashShift, POSReceipt, POSReceiptItem, CashMovement, HeldSale, POSReturn, POSReturnItem


@admin.register(POSTerminal)
class POSTerminalAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'warehouse', 'status', 'is_active']
    list_filter = ['status', 'is_active']
    search_fields = ['name', 'code', 'serial_number']


@admin.register(CashShift)
class CashShiftAdmin(admin.ModelAdmin):
    list_display = ['shift_number', 'terminal', 'cashier', 'status', 'opening_amount', 'closing_amount', 'difference', 'opened_at']
    list_filter = ['status']
    search_fields = ['shift_number']


@admin.register(POSReceipt)
class POSReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'terminal', 'status', 'payment_method', 'total', 'amount_paid', 'created_at']
    list_filter = ['status', 'payment_method']
    search_fields = ['receipt_number']


@admin.register(POSReceiptItem)
class POSReceiptItemAdmin(admin.ModelAdmin):
    list_display = ['receipt', 'product', 'quantity', 'unit_price', 'line_total']


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ['shift', 'movement_type', 'amount', 'reference_number', 'created_at']
    list_filter = ['movement_type']


@admin.register(HeldSale)
class HeldSaleAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'terminal', 'cashier', 'total', 'held_at']


@admin.register(POSReturn)
class POSReturnAdmin(admin.ModelAdmin):
    list_display = ['return_number', 'original_receipt', 'refund_amount', 'status', 'created_at']
    list_filter = ['status']


@admin.register(POSReturnItem)
class POSReturnItemAdmin(admin.ModelAdmin):
    list_display = ['pos_return', 'product', 'quantity', 'refund_amount']
