from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_index, name='reports_index'),

    # Sales
    path('sales/', views.report_sales, name='report_sales'),
    path('sales/by-product/', views.report_sales_by_product, name='report_sales_by_product'),
    path('sales/by-customer/', views.report_sales_by_customer, name='report_sales_by_customer'),

    # Purchases
    path('purchases/', views.report_purchases, name='report_purchases'),

    # Inventory
    path('inventory/', views.report_inventory, name='report_inventory'),
    path('inventory/movements/', views.report_stock_movement, name='report_stock_movement'),

    # Profit
    path('profit/', views.report_profit, name='report_profit'),

    # Finance
    path('finance/', views.report_finance, name='report_finance'),
    path('finance/cash-flow/', views.report_cash_flow, name='report_cash_flow'),
    path('finance/budget/', views.report_budget, name='report_budget'),

    # Analytics
    path('abc/', views.report_abc, name='report_abc'),
    path('xyz/', views.report_xyz, name='report_xyz'),
    path('abc-xyz/', views.report_abc_xyz, name='report_abc_xyz'),
    path('rfm/', views.report_rfm, name='report_rfm'),
    path('customers/', views.report_customers, name='report_customers'),
    path('suppliers/', views.report_suppliers, name='report_suppliers'),
    path('product-profitability/', views.report_product_profitability, name='report_product_profitability'),

    # Domain reports
    path('orders/', views.report_orders, name='report_orders'),
    path('pos/', views.report_pos, name='report_pos'),
    path('tasks/', views.report_tasks, name='report_tasks'),
    path('warehouses/', views.report_warehouses, name='report_warehouses'),
    path('kpi/', views.report_kpi, name='report_kpi'),

    # Saved reports
    path('saved/', views.saved_report_list, name='saved_report_list'),
    path('saved/create/', views.saved_report_create, name='saved_report_create'),
    path('saved/<int:pk>/run/', views.saved_report_run, name='saved_report_run'),
    path('saved/<int:pk>/delete/', views.saved_report_delete, name='saved_report_delete'),

    # Exports
    path('export/sales/', views.export_sales_csv, name='export_sales_csv'),
    path('export/purchases/', views.export_purchases_csv, name='export_purchases_csv'),
    path('export/inventory/', views.export_inventory_csv, name='export_inventory_csv'),
    path('export/stock-movements/', views.export_stock_movement_csv, name='export_stock_movement_csv'),
    path('export/abc/', views.export_abc_csv, name='export_abc_csv'),
    path('export/rfm/', views.export_rfm_csv, name='export_rfm_csv'),
]
