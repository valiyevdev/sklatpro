from django.db.models import Sum, Count, Avg, F, Q, Value, CharField, Max, Min, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay, TruncQuarter, Coalesce, Round
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import math
from collections import defaultdict
from .utils import get_prev_date_range, safe_div, safe_pct


def sales_summary(company, start_date, end_date):
    from sales.models import Sale, SaleItem, SaleReturn
    qs = Sale.objects.filter(company=company, date__gte=start_date, date__lte=end_date)
    agg = qs.aggregate(
        total_sales=Sum('total'),
        total_count=Count('id'),
        avg_sale=Avg('total'),
        total_discount=Sum('discount'),
        total_tax=Sum('tax'),
    )
    items_agg = SaleItem.objects.filter(
        sale__company=company, sale__date__gte=start_date, sale__date__lte=end_date
    ).aggregate(items_sold=Sum('quantity'))
    returns_agg = SaleReturn.objects.filter(
        company=company, created_at__date__gte=start_date, created_at__date__lte=end_date
    ).aggregate(total_returns=Sum('total'))

    gross = agg['total_sales'] or Decimal('0')
    discount = agg['total_discount'] or Decimal('0')
    returns_amt = returns_agg['total_returns'] or Decimal('0')
    net = gross - discount - returns_amt
    count = agg['total_count'] or 0
    items = items_agg['items_sold'] or 0
    avg = agg['avg_sale'] or Decimal('0')

    prev_start, prev_end = get_prev_date_range(start_date, end_date)
    prev = Sale.objects.filter(company=company, date__gte=prev_start, date__lte=prev_end)
    prev_total = prev.aggregate(t=Sum('total'))['t'] or Decimal('0')
    growth = safe_pct(gross - prev_total, prev_total)

    return {
        'gross_sales': gross, 'discounts': discount, 'returns': returns_amt,
        'net_sales': net, 'total_count': count, 'avg_sale': avg,
        'items_sold': items, 'total_tax': agg['total_tax'] or Decimal('0'),
        'prev_total': prev_total, 'growth': growth,
    }


def sales_trend(company, start_date, end_date, period='month'):
    from sales.models import Sale
    trunc = {'day': TruncDay, 'week': TruncWeek, 'month': TruncMonth}.get(period, TruncMonth)
    return list(
        Sale.objects.filter(company=company, date__gte=start_date, date__lte=end_date)
        .annotate(period=trunc('date'))
        .values('period')
        .annotate(total_sales=Sum('total'), count=Count('id'))
        .order_by('period')
    )
    for r in result:
        r['avg'] = r['total_sales'] / r['count'] if r['count'] else Decimal('0')
    return result


def sales_by_field(company, start_date, end_date, field, limit=10):
    from sales.models import Sale, SaleItem
    lookup = f'sale__{field}'
    return list(
        SaleItem.objects.filter(
            sale__company=company, sale__date__gte=start_date, sale__date__lte=end_date
        )
        .values(field)
        .annotate(total_amount=Sum('total'), total_qty=Sum('quantity'), count=Count('sale__id', distinct=True))
        .order_by('-total_amount')[:limit]
    )


def top_products(company, start_date, end_date, limit=10, sort='revenue'):
    from sales.models import SaleItem
    order = '-total_amount' if sort == 'revenue' else '-total_qty'
    return list(
        SaleItem.objects.filter(
            sale__company=company, sale__date__gte=start_date, sale__date__lte=end_date
        )
        .values('product__name')
        .annotate(total_amount=Sum('total'), total_qty=Sum('quantity'))
        .order_by(order)[:limit]
    )


def purchase_summary(company, start_date, end_date):
    from purchases.models import Purchase, PurchaseItem, PurchaseReturn
    qs = Purchase.objects.filter(company=company, order_date__gte=start_date, order_date__lte=end_date)
    agg = qs.aggregate(
        total_purchases=Sum('total'), total_count=Count('id'), avg_purchase=Avg('total'),
        total_discount=Sum('discount'), total_tax=Sum('tax'),
    )
    items_agg = PurchaseItem.objects.filter(
        purchase__company=company, purchase__order_date__gte=start_date, purchase__order_date__lte=end_date
    ).aggregate(items_purchased=Sum('quantity'))
    returns_agg = PurchaseReturn.objects.filter(
        company=company, created_at__date__gte=start_date, created_at__date__lte=end_date
    ).aggregate(total_returns=Sum('total'))

    total = agg['total_purchases'] or Decimal('0')
    discount = agg['total_discount'] or Decimal('0')
    returns_amt = returns_agg['total_returns'] or Decimal('0')
    net = total - discount - returns_amt

    prev_start, prev_end = get_prev_date_range(start_date, end_date)
    prev = Purchase.objects.filter(company=company, order_date__gte=prev_start, order_date__lte=prev_end)
    prev_total = prev.aggregate(t=Sum('total'))['t'] or Decimal('0')
    growth = safe_pct(total - prev_total, prev_total)

    return {
        'gross_purchases': total, 'discounts': discount, 'returns': returns_amt,
        'net_purchases': net, 'total_count': agg['total_count'] or 0,
        'avg_purchase': agg['avg_purchase'] or Decimal('0'),
        'items_purchased': items_agg['items_purchased'] or 0,
        'total_tax': agg['total_tax'] or Decimal('0'),
        'prev_total': prev_total, 'growth': growth,
    }


def purchases_by_supplier(company, start_date, end_date, limit=10):
    from purchases.models import PurchaseItem
    return list(
        PurchaseItem.objects.filter(
            purchase__company=company, purchase__order_date__gte=start_date, purchase__order_date__lte=end_date
        )
        .values('purchase__supplier__name')
        .annotate(total_amount=Sum('total'), total_qty=Sum('quantity'), count=Count('purchase__id', distinct=True))
        .order_by('-total_amount')[:limit]
    )


def inventory_summary(company):
    from inventory.models import StockLevel, StockMovement
    from products.models import Product
    products = Product.objects.filter(company=company)
    stock_levels = StockLevel.objects.filter(company=company)
    agg = stock_levels.aggregate(
        total_stock_value=Sum(F('quantity') * F('product__purchase_price')),
        total_products=Count('product', distinct=True),
    )
    low_stock = products.filter(max_stock__gt=0, quantity__lte=F('max_stock')).count()
    out_of_stock = products.filter(quantity=0).count()
    total_products = products.count()

    return {
        'total_stock_value': agg['total_stock_value'] or Decimal('0'),
        'total_products': agg['total_products'] or total_products,
        'low_stock_count': low_stock, 'out_of_stock_count': out_of_stock,
        'in_stock_count': total_products - out_of_stock,
    }


def stock_by_warehouse(company):
    from inventory.models import StockLevel
    return list(
        StockLevel.objects.filter(company=company)
        .values('warehouse__name')
        .annotate(
            total_qty=Sum('quantity'), total_reserved=Sum('reserved'),
            total_value=Sum(F('quantity') * F('product__purchase_price')),
            product_count=Count('product', distinct=True),
        )
        .order_by('-total_value')
    )


def stock_movement_report(company, start_date, end_date, limit=100):
    from inventory.models import StockMovement
    return list(
        StockMovement.objects.filter(company=company, created_at__date__gte=start_date, created_at__date__lte=end_date)
        .select_related('product', 'warehouse', 'user')
        .order_by('-created_at')[:limit]
    )


def low_stock_products(company):
    from products.models import Product
    return list(
        Product.objects.filter(company=company, max_stock__gt=0, quantity__lte=F('max_stock'))
        .order_by('quantity')[:20]
    )


def stock_by_category(company):
    from products.models import Product
    return list(
        Product.objects.filter(company=company)
        .values('category_fk__name')
        .annotate(
            total_qty=Sum('quantity'),
            total_value=Sum(F('quantity') * F('price')),
            product_count=Count('id'),
        )
        .order_by('-total_value')
    )


def finance_summary(company, start_date, end_date):
    from finance.models import FinancialTransaction, FinancialAccount
    income = FinancialTransaction.objects.filter(
        company=company, direction='in', date__gte=start_date, date__lte=end_date, status='approved'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    expense = FinancialTransaction.objects.filter(
        company=company, direction='out', date__gte=start_date, date__lte=end_date, status='approved'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    prev_start, prev_end = get_prev_date_range(start_date, end_date)
    prev_income = FinancialTransaction.objects.filter(
        company=company, direction='in', date__gte=prev_start, date__lte=prev_end, status='approved'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    prev_expense = FinancialTransaction.objects.filter(
        company=company, direction='out', date__gte=prev_start, date__lte=prev_end, status='approved'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    profit = income - expense
    prev_profit = prev_income - prev_expense
    margin = safe_pct(profit, income)
    growth = safe_pct(income - prev_income, prev_income) if prev_income else Decimal('0')

    accounts = FinancialAccount.objects.filter(company=company)
    total_balance = accounts.aggregate(t=Sum('opening_balance'))['t'] or Decimal('0')

    return {
        'income': income, 'expense': expense, 'profit': profit,
        'margin': margin, 'growth': growth,
        'prev_income': prev_income, 'prev_expense': prev_expense, 'prev_profit': prev_profit,
        'total_balance': total_balance,
    }


def cash_flow(company, start_date, end_date, period='month'):
    from finance.models import FinancialTransaction
    trunc_map = {'day': TruncDay, 'week': TruncWeek, 'month': TruncMonth, 'quarter': TruncQuarter}
    trunc = trunc_map.get(period, TruncMonth)
    rows = []
    income_qs = FinancialTransaction.objects.filter(
        company=company, direction='in', date__gte=start_date, date__lte=end_date, status='approved'
    ).annotate(period=trunc('date')).values('period').annotate(total=Sum('amount')).order_by('period')
    expense_qs = FinancialTransaction.objects.filter(
        company=company, direction='out', date__gte=start_date, date__lte=end_date, status='approved'
    ).annotate(period=trunc('date')).values('period').annotate(total=Sum('amount')).order_by('period')
    inc_map = {r['period']: r['total'] for r in income_qs}
    exp_map = {r['period']: r['total'] for r in expense_qs}
    all_periods = sorted(set(list(inc_map.keys()) + list(exp_map.keys())))
    for p in all_periods:
        inc = inc_map.get(p, Decimal('0'))
        exp = exp_map.get(p, Decimal('0'))
        rows.append({'period': p, 'income': inc, 'expense': exp, 'net': inc - exp})
    return rows


def budget_vs_actual(company, year):
    from finance.models import Budget
    budgets = Budget.objects.filter(company=company, year=year)
    return list(
        budgets.values('category__name', 'month')
        .annotate(planned=Sum('planned_amount'), actual=Sum('actual_amount'))
        .order_by('category__name', 'month')
    )


def abc_analysis(company, start_date, end_date, metric='revenue', top_n=50):
    from sales.models import SaleItem
    from products.models import Product
    items = SaleItem.objects.filter(
        sale__company=company, sale__date__gte=start_date, sale__date__lte=end_date
    ).values('product__name').annotate(
        total=Sum('total') if metric == 'revenue' else Sum('quantity')
    ).order_by('-total')[:top_n]
    total_all = sum(i['total'] for i in items) or Decimal('1')
    cumulative = Decimal('0')
    result = []
    for i, item in enumerate(items):
        cumulative += item['total']
        pct = safe_pct(item['total'], total_all)
        cum_pct = safe_pct(cumulative, total_all)
        if cum_pct <= 80:
            cls = 'A'
        elif cum_pct <= 95:
            cls = 'B'
        else:
            cls = 'C'
        result.append({
            'rank': i + 1, 'product': item['product__name'],
            'value': item['total'], 'pct': pct, 'cum_pct': cum_pct, 'class': cls,
        })
    return result


def xyz_analysis(company, start_date, end_date):
    from sales.models import SaleItem
    from django.db.models.functions import TruncMonth
    monthly = list(
        SaleItem.objects.filter(
            sale__company=company, sale__date__gte=start_date, sale__date__lte=end_date
        )
        .annotate(month=TruncMonth('sale__date'))
        .values('product__name', 'month')
        .annotate(total=Sum('quantity'))
        .order_by('product__name', 'month')
    )
    from collections import defaultdict
    product_months = defaultdict(list)
    for row in monthly:
        product_months[row['product__name']].append(float(row['total']))
    results = []
    for product, values in product_months.items():
        if len(values) < 2:
            continue
        avg = sum(values) / len(values)
        if avg == 0:
            cv = 0
        else:
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            cv = math.sqrt(variance) / avg if avg > 0 else 0
        if cv <= 0.2:
            cls = 'X'
        elif cv <= 0.5:
            cls = 'Y'
        else:
            cls = 'Z'
        results.append({'product': product, 'avg': round(avg, 1), 'cv': round(cv, 3), 'class': cls})
    results.sort(key=lambda x: x['cv'])
    return results


def abc_xyz_matrix(abc_list, xyz_list):
    xyz_map = {x['product']: x['class'] for x in xyz_list}
    matrix = defaultdict(lambda: {'count': 0, 'products': []})
    for item in abc_list:
        xyz_cls = xyz_map.get(item['product'], 'Z')
        key = item['class'] + xyz_cls
        matrix[key]['count'] += 1
        matrix[key]['products'].append(item['product'])
    return dict(matrix)


def rfm_analysis(company, start_date, end_date):
    from sales.models import Sale, Customer
    from django.db.models.functions import TruncMonth
    today = end_date
    customers = Customer.objects.filter(company=company)
    if not customers.exists():
        return {'segments': [], 'summary': {}}
    rfm_data = []
    for cust in customers:
        sales = Sale.objects.filter(company=company, customer=cust, date__lte=end_date)
        if not sales.exists():
            continue
        last_sale = sales.order_by('-date').first()
        recency_days = (today - last_sale.date).days if last_sale else 999
        frequency = sales.count()
        monetary = sales.aggregate(t=Sum('total'))['t'] or Decimal('0')
        rfm_data.append({'customer': cust.name, 'recency': recency_days, 'frequency': frequency, 'monetary': monetary})
    if not rfm_data:
        return {'segments': [], 'summary': {}}
    rfm_data.sort(key=lambda x: x['recency'])
    r_len = len(rfm_data)
    for i, d in enumerate(rfm_data):
        d['r_score'] = 5 - min(4, int(i / max(1, r_len // 5)))
    rfm_data.sort(key=lambda x: x['frequency'], reverse=True)
    for i, d in enumerate(rfm_data):
        d['f_score'] = 5 - min(4, int(i / max(1, r_len // 5)))
    rfm_data.sort(key=lambda x: x['monetary'], reverse=True)
    for i, d in enumerate(rfm_data):
        d['m_score'] = 5 - min(4, int(i / max(1, r_len // 5)))
    for d in rfm_data:
        d['rfm_score'] = d['r_score'] * 100 + d['f_score'] * 10 + d['m_score']
        avg = (d['r_score'] + d['f_score'] + d['m_score']) / 3
        if d['r_score'] >= 4 and d['f_score'] >= 4 and d['m_score'] >= 4:
            d['segment'] = 'Champions'
        elif d['r_score'] >= 3 and d['f_score'] >= 3:
            d['segment'] = 'Loyal Customers'
        elif d['r_score'] >= 4 and d['f_score'] <= 2:
            d['segment'] = 'New Customers'
        elif d['r_score'] <= 2 and d['f_score'] >= 3:
            d['segment'] = 'At Risk'
        elif d['r_score'] <= 2 and d['f_score'] <= 2:
            d['segment'] = 'Lost'
        elif d['r_score'] >= 3 and d['f_score'] <= 3:
            d['segment'] = 'Potential Loyalists'
        else:
            d['segment'] = 'Need Attention'
    segments = defaultdict(lambda: {'count': 0, 'revenue': Decimal('0'), 'customers': []})
    for d in rfm_data:
        seg = d['segment']
        segments[seg]['count'] += 1
        segments[seg]['revenue'] += d['monetary']
        segments[seg]['customers'].append(d['customer'])
    total_rev = sum(s['revenue'] for s in segments.values()) or Decimal('1')
    seg_list = []
    for name, data in sorted(segments.items(), key=lambda x: -x[1]['revenue']):
        seg_list.append({
            'name': name, 'count': data['count'],
            'revenue': data['revenue'],
            'pct_customers': safe_pct(data['count'], len(rfm_data)),
            'pct_revenue': safe_pct(data['revenue'], total_rev),
        })
    return {'segments': seg_list, 'summary': {'total_customers': len(rfm_data), 'total_revenue': total_rev}}


def customer_analytics(company, start_date, end_date):
    from sales.models import Sale, Customer
    from django.db.models.functions import TruncMonth
    total_customers = Customer.objects.filter(company=company).count()
    active = Sale.objects.filter(
        company=company, date__gte=start_date, date__lte=end_date
    ).values('customer').distinct().count()
    customer_sales = (
        Sale.objects.filter(company=company, date__gte=start_date, date__lte=end_date)
        .values('customer__name')
        .annotate(
            revenue=Sum('total'), orders=Count('id'),
            avg_order=Avg('total'),
        )
        .order_by('-revenue')[:20]
    )
    new_vs_repeat = Sale.objects.filter(
        company=company, date__gte=start_date, date__lte=end_date
    ).values('customer__name').annotate(order_count=Count('id'))
    new_count = new_vs_repeat.filter(order_count=1).count()
    repeat_count = new_vs_repeat.filter(order_count__gt=1).count()
    return {
        'total_customers': total_customers, 'active_customers': active,
        'new_customers': new_count, 'repeat_customers': repeat_count,
        'repeat_rate': safe_pct(repeat_count, active),
        'top_customers': list(customer_sales),
    }


def supplier_analytics(company, start_date, end_date):
    from purchases.models import Purchase, Supplier, PurchaseItem
    suppliers = Supplier.objects.filter(company=company)
    agg = Purchase.objects.filter(
        company=company, order_date__gte=start_date, order_date__lte=end_date
    ).values('supplier__name').annotate(
        total_value=Sum('total'), count=Count('id'), avg_value=Avg('total'),
    ).order_by('-total_value')
    debt_agg = Supplier.objects.filter(company=company).aggregate(total_debt=Sum('balance'))
    return {
        'supplier_data': list(agg),
        'total_suppliers': suppliers.count(),
        'total_debt': debt_agg['total_debt'] or Decimal('0'),
    }


def order_analytics(company, start_date, end_date):
    from orders.models import Order
    qs = Order.objects.filter(company=company, date__gte=start_date, date__lte=end_date)
    agg = qs.aggregate(
        order_count=Count('id'), confirmed=Count('id', filter=Q(status='confirmed')),
        completed=Count('id', filter=Q(status='delivered')),
        cancelled=Count('id', filter=Q(status='cancelled')),
        total_value=Sum('total'),
    )
    total = agg['order_count'] or 0
    completed = agg['completed'] or 0
    return {
        'total_orders': total, 'confirmed': agg['confirmed'] or 0,
        'completed': completed, 'cancelled': agg['cancelled'] or 0,
        'fulfillment_rate': safe_pct(completed, total),
        'total_value': agg['total_value'] or Decimal('0'),
    }


def pos_analytics(company, start_date, end_date):
    from pos.models import POSReceipt, CashShift
    receipts = POSReceipt.objects.filter(company=company, created_at__date__gte=start_date, created_at__date__lte=end_date)
    agg = receipts.aggregate(
        receipt_count=Count('id'), revenue=Sum('total'), avg_check=Avg('total'),
    )
    payment_methods = receipts.values('payment_method').annotate(count=Count('id'), total=Sum('total'))
    shifts = CashShift.objects.filter(company=company, opened_at__date__gte=start_date, opened_at__date__lte=end_date)
    shift_agg = shifts.aggregate(
        total_shifts=Count('id'),
        total_opening=Sum('opening_amount'),
        total_closing=Sum('closing_amount'),
        total_expected=Sum('expected_amount'),
    )
    return {
        'total_transactions': agg['receipt_count'] or 0, 'revenue': agg['revenue'] or Decimal('0'),
        'avg_check': agg['avg_check'] or Decimal('0'),
        'payment_methods': list(payment_methods),
        'total_shifts': shift_agg['total_shifts'] or 0,
    }


def task_analytics(company):
    from spiskalar.models import Task
    tasks = Task.objects.filter(company=company)
    agg = tasks.aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        overdue=Count('id', filter=Q(status__in=['pending', 'in_progress'], due_date__lt=timezone.now().date())),
        in_progress=Count('id', filter=Q(status='in_progress')),
    )
    by_type = tasks.values('task_type').annotate(count=Count('id')).order_by('-count')
    by_priority = tasks.values('priority').annotate(count=Count('id')).order_by('-count')
    by_employee = tasks.exclude(assigned_to=None).values(
        'assigned_to__first_name', 'assigned_to__last_name'
    ).annotate(
        total=Count('id'), completed=Count('id', filter=Q(status='completed'))
    ).order_by('-total')[:10]
    return {
        'total': agg['total'], 'completed': agg['completed'],
        'overdue': agg['overdue'], 'in_progress': agg['in_progress'],
        'completion_rate': safe_pct(agg['completed'], agg['total']),
        'by_type': list(by_type), 'by_priority': list(by_priority),
        'by_employee': list(by_employee),
    }


def warehouse_analytics(company):
    from inventory.models import StockLevel, StockMovement
    from products.models import Product
    warehouses = StockLevel.objects.filter(company=company).values('warehouse__name').annotate(
        total_qty=Sum('quantity'),
        total_value=Sum(F('quantity') * F('product__purchase_price')),
        product_count=Count('product', distinct=True),
    ).order_by('-total_value')
    low_by_warehouse = []
    for wh in warehouses:
        low = Product.objects.filter(
            company=company, max_stock__gt=0, quantity__lte=F('max_stock')
        ).count()
        low_by_warehouse.append({'warehouse': wh['warehouse__name'], 'low_stock': low})
    return {
        'warehouses': list(warehouses),
        'low_stock_by_warehouse': low_by_warehouse,
    }


def product_profitability(company, start_date, end_date, limit=20):
    from sales.models import SaleItem
    from purchases.models import PurchaseItem
    sales_data = (
        SaleItem.objects.filter(sale__company=company, sale__date__gte=start_date, sale__date__lte=end_date)
        .values('product__name')
        .annotate(revenue=Sum('total'), units_sold=Sum('quantity'), avg_price=Avg('unit_price'))
    )
    purchase_data = {
        row['product__name']: row['cost']
        for row in PurchaseItem.objects.filter(
            purchase__company=company, purchase__order_date__gte=start_date, purchase__order_date__lte=end_date
        ).values('product__name').annotate(cost=Sum('total'))
    }
    results = []
    for item in sales_data:
        name = item['product__name']
        revenue = item['revenue'] or Decimal('0')
        cost = purchase_data.get(name, Decimal('0'))
        profit = revenue - cost
        margin = safe_pct(profit, revenue) if revenue else Decimal('0')
        results.append({
            'product': name, 'revenue': revenue, 'cost': cost,
            'profit': profit, 'margin': margin,
            'units_sold': item['units_sold'] or 0,
        })
    results.sort(key=lambda x: x['profit'], reverse=True)
    return results[:limit]


def kpi_summary(company, start_date, end_date):
    sales = sales_summary(company, start_date, end_date)
    purchases = purchase_summary(company, start_date, end_date)
    fin = finance_summary(company, start_date, end_date)
    inv = inventory_summary(company)
    from sales.models import Customer
    new_customers = Customer.objects.filter(
        company=company, created_at__date__gte=start_date, created_at__date__lte=end_date
    ).count()
    return {
        'sales': sales, 'purchases': purchases, 'finance': fin,
        'inventory': inv, 'new_customers': new_customers,
    }
