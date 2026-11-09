from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Inventory
    path('inventory/', views.inventory_overview, name='inventory_overview'),
    path('inventory/table/', views.inventory_table, name='inventory_table'),

    # Stock alerts
    path('inventory/low-stock/', views.low_stock_list, name='low_stock_list'),
    path('inventory/out-of-stock/', views.out_of_stock_list, name='out_of_stock_list'),
    path('inventory/overstock/', views.overstock_list, name='overstock_list'),

    # Movement history
    path('inventory/movements/', views.movement_history, name='movement_history'),

    # Adjustments
    path('inventory/adjustments/', views.adjustment_list, name='adjustment_list'),
    path('inventory/adjustments/create/', views.adjustment_create, name='adjustment_create'),
    path('inventory/adjustments/<int:pk>/', views.adjustment_detail, name='adjustment_detail'),
    path('inventory/adjustments/<int:pk>/add-item/', views.adjustment_add_item, name='adjustment_add_item'),
    path('inventory/adjustments/<int:pk>/submit/', views.adjustment_submit, name='adjustment_submit'),
    path('inventory/adjustments/<int:pk>/approve/', views.adjustment_approve, name='adjustment_approve'),

    # Inventory counts (stocktake)
    path('inventory/counts/', views.count_list, name='count_list'),
    path('inventory/counts/create/', views.count_create, name='count_create'),
    path('inventory/counts/<int:pk>/', views.count_detail, name='count_detail'),
    path('inventory/counts/<int:pk>/start/', views.count_start, name='count_start'),
    path('inventory/counts/<int:pk>/item/<int:item_pk>/', views.count_item_update, name='count_item_update'),
    path('inventory/counts/<int:pk>/submit/', views.count_submit, name='count_submit'),
    path('inventory/counts/<int:pk>/approve/', views.count_approve, name='count_approve'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('stock-in/', views.stock_in, name='stock_in'),
    path('stock-out/', views.stock_out, name='stock_out'),

    # Business insights
    path('business-insights/', views.business_insights, name='business_insights'),
]
