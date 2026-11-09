from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, F
from django.utils import timezone
from .utils import get_date_range, get_company, fmt_number
from core.translations import t as _t
from . import services
from .models import SavedReport
from .forms import ReportFilterForm, SavedReportForm
from .export import export_csv


def _ctx(request, **extra):
    company = get_company(request)
    start_date, end_date = get_date_range(request)
    ctx = {
        'company': company, 'start_date': start_date, 'end_date': end_date,
        'now': timezone.now(),
    }
    ctx.update(extra)
    return ctx


@login_required
@never_cache
def reports_index(request):
    company = get_company(request)
    start_date, end_date = get_date_range(request)
    kpis = services.kpi_summary(company, start_date, end_date)
    saved = SavedReport.objects.filter(company=company, owner=request.user)[:10]
    return render(request, 'reports/reports_index.html', {
        'kpis': kpis, 'saved_reports': saved,
        'start_date': start_date, 'end_date': end_date,
    })


@login_required
@never_cache
def report_sales(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    summary = services.sales_summary(company, sd, ed)
    trend = services.sales_trend(company, sd, ed, 'month')
    top_prods = services.top_products(company, sd, ed, 10)
    by_customer = services.sales_by_field(company, sd, ed, 'sale__customer__name', 10)
    by_employee = services.sales_by_field(company, sd, ed, 'sale__created_by__email', 10)
    return render(request, 'reports/report_sales.html', {
        'start_date': sd, 'end_date': ed,
        'summary': summary, 'trend': trend,
        'top_products': top_prods, 'by_customer': by_customer, 'by_employee': by_employee,
    })


@login_required
@never_cache
def report_sales_by_product(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    top_prods = services.top_products(company, sd, ed, 20)
    by_cat = services.sales_by_field(company, sd, ed, 'product__category_fk__name', 10)
    return render(request, 'reports/report_sales_by_product.html', {
        'start_date': sd, 'end_date': ed,
        'top_products': top_prods, 'by_category': by_cat,
    })


@login_required
@never_cache
def report_sales_by_customer(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    by_cust = services.sales_by_field(company, sd, ed, 'sale__customer__name', 20)
    return render(request, 'reports/report_sales_by_customer.html', {
        'start_date': sd, 'end_date': ed, 'by_customer': by_cust,
    })


@login_required
@never_cache
def report_purchases(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    summary = services.purchase_summary(company, sd, ed)
    by_supplier = services.purchases_by_supplier(company, sd, ed, 10)
    trend = services.sales_trend(company, sd, ed, 'month')
    return render(request, 'reports/report_purchases.html', {
        'start_date': sd, 'end_date': ed,
        'summary': summary, 'by_supplier': by_supplier, 'trend': trend,
    })


@login_required
@never_cache
def report_inventory(request):
    company = get_company(request)
    summary = services.inventory_summary(company)
    by_warehouse = services.stock_by_warehouse(company)
    by_category = services.stock_by_category(company)
    low_stock = services.low_stock_products(company)
    return render(request, 'reports/report_inventory.html', {
        'summary': summary, 'by_warehouse': by_warehouse,
        'by_category': by_category, 'low_stock': low_stock,
    })


@login_required
@never_cache
def report_stock_movement(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    movements = services.stock_movement_report(company, sd, ed, 200)
    return render(request, 'reports/report_stock_movement.html', {
        'start_date': sd, 'end_date': ed, 'movements': movements,
    })


@login_required
@never_cache
def report_profit(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    summary = services.sales_summary(company, sd, ed)
    purch = services.purchase_summary(company, sd, ed)
    net_sales = summary['net_sales']
    cogs = purch['net_purchases']
    gross_profit = net_sales - cogs
    margin_data = services.safe_pct(gross_profit, net_sales) if net_sales else 0
    trend = []
    sales_trend = services.sales_trend(company, sd, ed, 'month')
    for row in sales_trend:
        trend.append({'period': row['period'], 'revenue': row['total_sales'],
                       'cost': cogs, 'profit': row['total_sales'] - cogs})
    return render(request, 'reports/report_profit.html', {
        'start_date': sd, 'end_date': ed,
        'total_revenue': net_sales, 'total_cost': cogs,
        'net_profit': gross_profit, 'profit_margin': margin_data,
        'monthly_profit': trend,
    })


@login_required
@never_cache
def report_finance(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    summary = services.finance_summary(company, sd, ed)
    return render(request, 'reports/report_finance.html', {
        'start_date': sd, 'end_date': ed, 'summary': summary,
    })


@login_required
@never_cache
def report_cash_flow(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    period = request.GET.get('period', 'month')
    flow = services.cash_flow(company, sd, ed, period)
    total_in = sum(r['income'] for r in flow)
    total_out = sum(r['expense'] for r in flow)
    return render(request, 'reports/report_cash_flow.html', {
        'start_date': sd, 'end_date': ed, 'period': period,
        'flow': flow, 'total_in': total_in, 'total_out': total_out, 'net': total_in - total_out,
    })


@login_required
@never_cache
def report_budget(request):
    company = get_company(request)
    year = int(request.GET.get('year', timezone.now().year))
    budgets = services.budget_vs_actual(company, year)
    return render(request, 'reports/report_budget.html', {
        'year': year, 'budgets': budgets,
    })


@login_required
@never_cache
def report_abc(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    metric = request.GET.get('metric', 'revenue')
    abc = services.abc_analysis(company, sd, ed, metric)
    a_count = sum(1 for x in abc if x['class'] == 'A')
    b_count = sum(1 for x in abc if x['class'] == 'B')
    c_count = sum(1 for x in abc if x['class'] == 'C')
    return render(request, 'reports/report_abc.html', {
        'start_date': sd, 'end_date': ed, 'metric': metric,
        'abc': abc, 'a_count': a_count, 'b_count': b_count, 'c_count': c_count,
    })


@login_required
@never_cache
def report_xyz(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    xyz = services.xyz_analysis(company, sd, ed)
    x_count = sum(1 for x in xyz if x['class'] == 'X')
    y_count = sum(1 for x in xyz if x['class'] == 'Y')
    z_count = sum(1 for x in xyz if x['class'] == 'Z')
    return render(request, 'reports/report_xyz.html', {
        'start_date': sd, 'end_date': ed,
        'xyz': xyz, 'x_count': x_count, 'y_count': y_count, 'z_count': z_count,
    })


@login_required
@never_cache
def report_abc_xyz(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    abc = services.abc_analysis(company, sd, ed, 'revenue', 50)
    xyz = services.xyz_analysis(company, sd, ed)
    matrix = services.abc_xyz_matrix(abc, xyz)
    all_combos = ['AX', 'AY', 'AZ', 'BX', 'BY', 'BZ', 'CX', 'CY', 'CZ']
    matrix_dict = {}
    for combo in all_combos:
        data = matrix.get(combo, {'count': 0, 'products': []})
        matrix_dict[combo] = data
    return render(request, 'reports/report_abc_xyz.html', {
        'start_date': sd, 'end_date': ed, 'matrix_dict': matrix_dict,
    })


@login_required
@never_cache
def report_rfm(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    rfm = services.rfm_analysis(company, sd, ed)
    return render(request, 'reports/report_rfm.html', {
        'start_date': sd, 'end_date': ed, 'rfm': rfm,
    })


@login_required
@never_cache
def report_customers(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    analytics = services.customer_analytics(company, sd, ed)
    return render(request, 'reports/report_customers.html', {
        'start_date': sd, 'end_date': ed, 'analytics': analytics,
    })


@login_required
@never_cache
def report_suppliers(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    analytics = services.supplier_analytics(company, sd, ed)
    return render(request, 'reports/report_suppliers.html', {
        'start_date': sd, 'end_date': ed, 'analytics': analytics,
    })


@login_required
@never_cache
def report_product_profitability(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    products = services.product_profitability(company, sd, ed, 20)
    return render(request, 'reports/report_product_profitability.html', {
        'start_date': sd, 'end_date': ed, 'products': products,
    })


@login_required
@never_cache
def report_orders(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    analytics = services.order_analytics(company, sd, ed)
    return render(request, 'reports/report_orders.html', {
        'start_date': sd, 'end_date': ed, 'analytics': analytics,
    })


@login_required
@never_cache
def report_pos(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    analytics = services.pos_analytics(company, sd, ed)
    return render(request, 'reports/report_pos.html', {
        'start_date': sd, 'end_date': ed, 'analytics': analytics,
    })


@login_required
@never_cache
def report_tasks(request):
    company = get_company(request)
    analytics = services.task_analytics(company)
    return render(request, 'reports/report_tasks.html', {
        'analytics': analytics,
    })


@login_required
@never_cache
def report_warehouses(request):
    company = get_company(request)
    analytics = services.warehouse_analytics(company)
    return render(request, 'reports/report_warehouses.html', {
        'analytics': analytics,
    })


@login_required
@never_cache
def report_kpi(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    kpis = services.kpi_summary(company, sd, ed)
    return render(request, 'reports/report_kpi.html', {
        'start_date': sd, 'end_date': ed, 'kpis': kpis,
    })


# === SAVED REPORTS ===

@login_required
@never_cache
def saved_report_list(request):
    company = get_company(request)
    reports = SavedReport.objects.filter(company=company, owner=request.user)
    return render(request, 'reports/saved_report_list.html', {'reports': reports})


@login_required
@never_cache
def saved_report_create(request):
    company = get_company(request)
    if request.method == 'POST':
        form = SavedReportForm(request.POST)
        if form.is_valid():
            rpt = form.save(commit=False)
            rpt.company = company
            rpt.owner = request.user
            rpt.save()
            messages.success(request, _t('report_saved'))
            return redirect('reports:saved_report_list')
    else:
        form = SavedReportForm()
    return render(request, 'reports/saved_report_form.html', {'form': form})


@login_required
@never_cache
def saved_report_run(request, pk):
    company = get_company(request)
    rpt = get_object_or_404(SavedReport, pk=pk, company=company)
    report_views = {
        'sales_summary': report_sales,
        'sales_trend': report_sales,
        'purchase_summary': report_purchases,
        'inventory_summary': report_inventory,
        'finance_summary': report_finance,
        'abc_analysis': report_abc,
        'xyz_analysis': report_xyz,
        'rfm_analysis': report_rfm,
        'customer_analytics': report_customers,
        'supplier_analytics': report_suppliers,
        'order_analytics': report_orders,
        'pos_analytics': report_pos,
        'task_analytics': report_tasks,
        'warehouse_analytics': report_warehouses,
        'kpi_summary': report_kpi,
        'cash_flow': report_cash_flow,
        'budget_vs_actual': report_budget,
        'product_profitability': report_product_profitability,
    }
    view_func = report_views.get(rpt.report_type)
    if view_func:
        for key, val in rpt.filters.items():
            request.GET = request.GET.copy()
            request.GET[key] = val
        return view_func(request)
    return redirect('reports:reports_index')


@login_required
@require_POST
def saved_report_delete(request, pk):
    company = get_company(request)
    rpt = get_object_or_404(SavedReport, pk=pk, company=company, owner=request.user)
    rpt.delete()
    messages.success(request, _t('report_deleted'))
    return redirect('reports:saved_report_list')


# === EXPORT VIEWS ===

@login_required
def export_sales_csv(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    from sales.models import Sale
    sales = Sale.objects.filter(company=company, date__gte=sd, date__lte=ed).values(
        'reference', 'date', 'customer__name', 'total', 'discount', 'tax', 'payment_status', 'status'
    )
    return export_csv(list(sales), 'sales_report')


@login_required
def export_purchases_csv(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    from purchases.models import Purchase
    purchases = Purchase.objects.filter(company=company, order_date__gte=sd, order_date__lte=ed).values(
        'reference', 'order_date', 'supplier__name', 'total', 'discount', 'tax', 'payment_status', 'status'
    )
    return export_csv(list(purchases), 'purchase_report')


@login_required
def export_inventory_csv(request):
    company = get_company(request)
    from products.models import Product
    products = Product.objects.filter(company=company).values(
        'name', 'sku', 'category_fk__name', 'quantity', 'price', 'purchase_price', 'min_stock', 'max_stock'
    )
    return export_csv(list(products), 'inventory_report')


@login_required
def export_stock_movement_csv(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    from inventory.models import StockMovement
    movements = StockMovement.objects.filter(
        company=company, created_at__date__gte=sd, created_at__date__lte=ed
    ).values(
        'created_at', 'product__name', 'warehouse__name', 'direction',
        'movement_type', 'quantity', 'before_quantity', 'after_quantity', 'user__email'
    )
    return export_csv(list(movements), 'stock_movements')


@login_required
def export_abc_csv(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    metric = request.GET.get('metric', 'revenue')
    abc = services.abc_analysis(company, sd, ed, metric)
    return export_csv(abc, 'abc_analysis')


@login_required
def export_rfm_csv(request):
    company = get_company(request)
    sd, ed = get_date_range(request)
    rfm = services.rfm_analysis(company, sd, ed)
    return export_csv(rfm.get('segments', []), 'rfm_analysis')
