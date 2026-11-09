from django.contrib import admin
from .models import (CustomerDebt, SupplierDebt, Payment, FinancialAccount,
    FinancialTransaction, AccountTransfer, ExpenseCategory, IncomeCategory,
    Budget, ExchangeRate, PurchasePayment)

@admin.register(CustomerDebt)
class CustomerDebtAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'phone_number', 'debt_amount', 'paid_amount', 'remaining_balance', 'due_date', 'payment_status', 'created_at']
    list_filter = ['payment_status', 'due_date', 'created_at']
    search_fields = ['customer_name', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'

@admin.register(SupplierDebt)
class SupplierDebtAdmin(admin.ModelAdmin):
    list_display = ['supplier_name', 'amount_owed', 'paid_amount', 'remaining_balance', 'due_date', 'payment_status', 'created_at']
    list_filter = ['payment_status', 'due_date', 'created_at']
    search_fields = ['supplier_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_type', 'amount', 'payment_date', 'created_at', 'created_by']
    list_filter = ['payment_type', 'payment_date', 'created_at']
    search_fields = ['notes']
    readonly_fields = ['created_at', 'created_by']
    date_hierarchy = 'payment_date'

@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'account_type', 'currency', 'opening_balance', 'is_active', 'created_at']
    list_filter = ['account_type', 'is_active']
    search_fields = ['name', 'code']

@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'txn_type', 'direction', 'amount', 'account', 'category', 'payment_method', 'status']
    list_filter = ['txn_type', 'direction', 'status', 'date']
    search_fields = ['description', 'reference_number']
    date_hierarchy = 'date'

@admin.register(AccountTransfer)
class AccountTransferAdmin(admin.ModelAdmin):
    list_display = ['date', 'from_account', 'to_account', 'amount', 'status']
    list_filter = ['status', 'date']
    date_hierarchy = 'date'

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    search_fields = ['name', 'code']

@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active']
    search_fields = ['name', 'code']

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'period_type', 'year', 'month', 'planned_amount', 'actual_amount', 'status']
    list_filter = ['period_type', 'year', 'status']
    search_fields = ['name']

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['base_currency', 'quote_currency', 'rate', 'date', 'source']
    list_filter = ['base_currency', 'quote_currency']
    date_hierarchy = 'date'

@admin.register(PurchasePayment)
class PurchasePaymentAdmin(admin.ModelAdmin):
    list_display = ['purchase', 'amount', 'payment_method', 'payment_date', 'account']
    list_filter = ['payment_method', 'payment_date']
    date_hierarchy = 'payment_date'

