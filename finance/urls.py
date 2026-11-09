from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.financial_dashboard, name='financial_dashboard'),

    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/create/', views.transaction_create, name='transaction_create'),

    path('accounts/', views.account_list, name='account_list'),
    path('accounts/create/', views.account_create, name='account_create'),
    path('accounts/<int:pk>/', views.account_detail, name='account_detail'),
    path('accounts/<int:pk>/edit/', views.account_edit, name='account_edit'),

    path('transfers/create/', views.transfer_create, name='transfer_create'),

    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/create/', views.expense_create, name='expense_create'),
    path('expense-categories/', views.expense_category_list, name='expense_category_list'),

    path('income/', views.income_list, name='income_list'),
    path('income/create/', views.income_create, name='income_create'),
    path('income-categories/', views.income_category_list, name='income_category_list'),

    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/create/', views.budget_create, name='budget_create'),

    path('reports/', views.reports_hub, name='reports_hub'),
    path('reports/profit-loss/', views.profit_loss_report, name='profit_loss_report'),
    path('reports/cash-flow/', views.cash_flow_report, name='cash_flow_report'),
    path('reports/receivables-aging/', views.receivables_aging, name='receivables_aging'),
    path('reports/payables-aging/', views.payables_aging, name='payables_aging'),
    path('reports/customer-statement/<int:pk>/', views.customer_statement, name='customer_statement'),
    path('reports/supplier-statement/<int:pk>/', views.supplier_statement, name='supplier_statement'),
    path('reports/account-statement/<int:pk>/', views.account_statement, name='account_statement'),

    path('customer-debts/', views.customer_debt_list, name='customer_debt_list'),
    path('customer-debts/create/', views.customer_debt_create, name='customer_debt_create'),
    path('customer-debts/<int:pk>/', views.customer_debt_detail, name='customer_debt_detail'),
    path('customer-debts/<int:pk>/update/', views.customer_debt_update, name='customer_debt_update'),
    path('customer-debts/<int:pk>/delete/', views.customer_debt_delete, name='customer_debt_delete'),
    path('customer-debts/<str:customer_name>/profile/', views.customer_profile, name='customer_profile'),

    path('supplier-debts/', views.supplier_debt_list, name='supplier_debt_list'),
    path('supplier-debts/create/', views.supplier_debt_create, name='supplier_debt_create'),
    path('supplier-debts/<int:pk>/', views.supplier_debt_detail, name='supplier_debt_detail'),
    path('supplier-debts/<int:pk>/update/', views.supplier_debt_update, name='supplier_debt_update'),
    path('supplier-debts/<int:pk>/delete/', views.supplier_debt_delete, name='supplier_debt_delete'),
    path('supplier-debts/<str:supplier_name>/profile/', views.supplier_profile, name='supplier_profile'),

    path('payments/<str:debt_type>/<int:debt_id>/create/', views.payment_create, name='payment_create'),
]
