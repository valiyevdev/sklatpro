from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['product', 'transaction_type', 'quantity', 'user', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['product__name', 'user__username']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
