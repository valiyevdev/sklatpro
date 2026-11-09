from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    # POS WORKSPACE (full-screen cashier interface)
    path('workspace/', views.workspace, name='workspace'),
    path('nasiya-daftari/', views.debt_ledger, name='debt_ledger'),
    path('nasiya-daftari/mijoz/<int:customer_id>/', views.customer_profile, name='customer_profile'),

    # POS MANAGEMENT (admin-style pages)
    path('', views.pos_dashboard, name='pos_dashboard'),
    path('terminals/', views.terminal_list, name='terminal_list'),
    path('terminals/create/', views.terminal_create, name='terminal_create'),
    path('terminals/<int:pk>/', views.terminal_detail, name='terminal_detail'),
    path('terminals/<int:pk>/update/', views.terminal_update, name='terminal_update'),
    path('terminals/<int:pk>/delete/', views.terminal_delete, name='terminal_delete'),
    path('shifts/', views.shift_list, name='shift_list'),
    path('shifts/<int:pk>/', views.shift_detail, name='shift_detail'),
    path('receipts/', views.receipt_list, name='receipt_list'),
    path('receipts/<int:pk>/', views.receipt_detail, name='receipt_detail'),
    path('receipts/<int:pk>/cancel/', views.receipt_cancel, name='receipt_cancel'),

    # POS API (JSON endpoints for workspace)
    path('api/search/', views.api_product_search, name='api_product_search'),
    path('api/barcode/', views.api_barcode_scan, name='api_barcode_scan'),
    path('api/customer/search/', views.api_customer_search, name='api_customer_search'),
    path('api/customer/create/', views.api_customer_create, name='api_customer_create'),
    path('api/debt/payment/', views.api_debt_payment, name='api_debt_payment'),
    path('api/cart/add/', views.api_cart_add, name='api_cart_add'),
    path('api/cart/update/', views.api_cart_update, name='api_cart_update'),
    path('api/cart/remove/', views.api_cart_remove, name='api_cart_remove'),
    path('api/cart/clear/', views.api_cart_clear, name='api_cart_clear'),
    path('api/cart/customer/', views.api_cart_customer, name='api_cart_customer'),
    path('api/cart/discount/', views.api_cart_discount, name='api_cart_discount'),
    path('api/product/create/', views.api_product_create, name='api_product_create'),
    path('api/product/quick/', views.api_quick_item, name='api_quick_item'),
    path('api/product/import/', views.api_product_import, name='api_product_import'),
    path('api/checkout/', views.api_checkout, name='api_checkout'),
    path('api/create-sale/', views.api_checkout, name='create_sale'),
    path('api/hold/', views.api_hold_sale, name='api_hold_sale'),
    path('api/resume/', views.api_resume_sale, name='api_resume_sale'),
    path('api/hold/delete/', views.api_delete_held, name='api_delete_held'),
    path('api/shift/open/', views.api_open_shift, name='api_open_shift'),
    path('api/shift/close/', views.api_close_shift, name='api_close_shift'),
    path('api/shift/summary/', views.api_shift_summary, name='api_shift_summary'),
    path('api/shift/expense/', views.api_shift_expense, name='api_shift_expense'),
    path('api/low-stock/', views.api_low_stock, name='api_low_stock'),
    path('api/low-stock/export/', views.api_low_stock_export, name='api_low_stock_export'),
    path('api/return/', views.api_return_sale, name='api_return_sale'),
    path('api/stock-in/', views.api_stock_in, name='api_stock_in'),
]
