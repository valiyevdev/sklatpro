from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction, IntegrityError
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
import csv
import io
import json
import uuid

from .models import POSTerminal, CashShift, POSReceipt, POSReceiptItem, CashMovement, HeldSale, POSReturn, POSReturnItem
from .forms import POSTerminalForm, CashShiftOpenForm, CashShiftCloseForm
from sales.models import Customer, Sale, SaleItem, SalePayment, Debt, DebtPayment
from products.models import Product, ProductVariant, Category, Unit
from warehouses.models import Warehouse
from inventory.models import StockEngine, StockLevel
from pricing.engine import resolve_price, PriceResult
from finance.models import FinancialTransaction, FinancialAccount
from activity.models import Activity
from core.translations import get_translation

User = get_user_model()


# ============================================================
# HELPERS
# ============================================================

def _lang(request):
    return request.session.get('language', 'uz')


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if company:
        return company
    if request.user.is_superuser:
        messages.warning(request, get_translation('superuser_no_company_warning', _lang(request)))
        from users.models import Company
        return Company.objects.first()
    return None


def _is_owner(user):
    return user.is_superuser or user.is_company_admin()


def _can_manage_stock(user):
    return _is_owner(user) or user.is_manager()


def _next_receipt_number(company):
    today = timezone.now().strftime('%Y%m%d')
    if company:
        count = POSReceipt.objects.filter(company=company, created_at__date=timezone.now().date()).count()
    else:
        count = POSReceipt.objects.filter(created_at__date=timezone.now().date()).count()
    return f"POS-{today}-{count + 1:04d}"


def _next_shift_number(company):
    today = timezone.now().strftime('%Y%m%d')
    if company:
        count = CashShift.objects.filter(company=company, opened_at__date=timezone.now().date()).count()
    else:
        count = CashShift.objects.filter(opened_at__date=timezone.now().date()).count()
    return f"SH-{today}-{count + 1:03d}"


def _next_return_number(company):
    today = timezone.now().strftime('%Y%m%d')
    if company:
        count = POSReturn.objects.filter(company=company, created_at__date=timezone.now().date()).count()
    else:
        count = POSReturn.objects.filter(created_at__date=timezone.now().date()).count()
    return f"RET-{today}-{count + 1:04d}"


def _calc_cart_totals(cart, company=None):
    subtotal = Decimal('0')
    item_discount_amount = Decimal('0')
    for item in cart.get('items', []):
        price = Decimal(item.get('unit_price', 0))
        qty = Decimal(item.get('quantity', 0))
        discount = Decimal(item.get('discount', 0))
        subtotal += price * qty
        item_discount_amount += discount

    subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    item_discount_amount = item_discount_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    discount_amount = Decimal(cart.get('discount_amount', 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    tax_rate = getattr(company, 'pos_tax_rate', Decimal('0')) if company else Decimal('0')
    total_discount = item_discount_amount + discount_amount
    taxable = subtotal - total_discount
    if taxable < 0:
        taxable = Decimal('0')
    tax_amount = (taxable * tax_rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = (taxable + tax_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    customer = Customer.objects.filter(pk=cart.get('customer_id'), company=company, is_active=True).first() if cart.get('customer_id') and company else None
    return {
        'items': cart.get('items', []),
        'item_count': len(cart.get('items', [])),
        'subtotal': str(subtotal),
        'discount_amount': str(total_discount),
        'order_discount_amount': str(discount_amount),
        'item_discount_amount': str(item_discount_amount),
        'tax_rate': str(tax_rate),
        'tax_amount': str(tax_amount),
        'total': str(total),
        'customer_id': cart.get('customer_id'),
        'coupon_code': cart.get('coupon_code', ''),
        'discount_mode': cart.get('discount_mode', 'amount'),
        'discount_value': str(cart.get('discount_value', discount_amount)),
        'customer_name': customer.name if customer else '',
        'customer_balance': str(customer.outstanding_balance) if customer else '0',
    }


def _shift_summary(shift):
    receipts = POSReceipt.objects.filter(shift=shift, status='completed').select_related('sale').prefetch_related('items__product', 'sale__payments')
    total = receipts.aggregate(value=Sum('total'))['value'] or Decimal('0')
    count = receipts.count()
    cash = card = transfer = credit = expenses = profit = Decimal('0')
    for receipt in receipts:
        if receipt.sale and receipt.sale.payment_terms == 'credit':
            credit += receipt.total
        if receipt.sale:
            for payment in receipt.sale.payments.all():
                if payment.payment_method == 'cash': cash += payment.amount
                elif payment.payment_method == 'card': card += payment.amount
                elif payment.payment_method in ('transfer', 'online'): transfer += payment.amount
        for item in receipt.items.all():
            profit += (item.unit_price - item.product.purchase_price) * item.quantity - item.discount
    expense_txns = FinancialTransaction.objects.filter(company=shift.company, reference_type='CashShift', reference_id=shift.pk, direction='expense', status='completed')
    expenses = expense_txns.aggregate(value=Sum('amount'))['value'] or Decimal('0')
    movements_in = CashMovement.objects.filter(shift=shift, movement_type__in=['opening', 'sale_cash', 'cash_in']).aggregate(value=Sum('amount'))['value'] or Decimal('0')
    movements_out = CashMovement.objects.filter(shift=shift, movement_type__in=['refund', 'cash_out']).aggregate(value=Sum('amount'))['value'] or Decimal('0')
    expected_cash = movements_in - movements_out
    return {'total': total, 'count': count, 'cash': cash, 'card': card, 'transfer': transfer, 'credit': credit, 'expenses': expenses, 'expected_cash': expected_cash, 'profit': profit}


def _low_stock_products(company, warehouse=None):
    levels = StockLevel.objects.filter(company=company).select_related('product', 'warehouse')
    if warehouse:
        levels = levels.filter(warehouse=warehouse)
    return levels.filter(quantity__lte=F('product__min_stock') + F('reserved'))


# ============================================================
# POS WORKSPACE (Full-screen cashier interface)
# ============================================================

@login_required
@never_cache
def workspace(request):
    company = _get_company(request)
    if not company and not request.user.is_superuser:
        return redirect('login')

    terminal_id = request.GET.get('terminal') or request.session.get('pos_terminal_id')

    terminal = None
    open_shift = None
    if terminal_id:
        if company:
            terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).first()
        else:
            terminal = POSTerminal.objects.filter(pk=terminal_id).first()
        if terminal:
            request.session['pos_terminal_id'] = terminal.pk
            open_shift = CashShift.objects.filter(
                terminal=terminal, cashier=request.user, status='open'
            ).first()

    if company:
        terminals = POSTerminal.objects.filter(company=company, is_active=True, status='active')
    else:
        terminals = POSTerminal.objects.filter(is_active=True, status='active')

    held_sales = []
    held_sales_query = HeldSale.objects.filter(cashier=request.user, company=company)
    if terminal:
        held_sales_query = held_sales_query.filter(terminal=terminal)
    else:
        held_sales_query = held_sales_query.filter(terminal__isnull=True)
    held_sales = held_sales_query.order_by('-held_at')

    from products.models import Category
    categories = Category.objects.filter(is_active=True)
    if company:
        categories = categories.filter(Q(company=company) | Q(company__isnull=True))
    categories = categories[:20]

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})
    today = timezone.localdate()
    today_receipts = POSReceipt.objects.filter(company=company, created_at__date=today, status='completed') if company else POSReceipt.objects.none()
    today_summary = {'total': today_receipts.aggregate(value=Sum('total'))['value'] or Decimal('0'), 'count': today_receipts.count(), 'cash': Decimal('0'), 'card': Decimal('0'), 'transfer': Decimal('0'), 'credit': Decimal('0'), 'profit': Decimal('0')}
    for receipt in today_receipts.select_related('sale').prefetch_related('sale__payments', 'items__product'):
        if receipt.sale and receipt.sale.payment_terms == 'credit': today_summary['credit'] += receipt.total
        if receipt.sale:
            for payment in receipt.sale.payments.all():
                if payment.payment_method == 'cash': today_summary['cash'] += payment.amount
                elif payment.payment_method == 'card': today_summary['card'] += payment.amount
                elif payment.payment_method in ('transfer', 'online'): today_summary['transfer'] += payment.amount
        for item in receipt.items.all(): today_summary['profit'] += (item.unit_price - item.product.purchase_price) * item.quantity - item.discount
    low_stock = _low_stock_products(company, terminal.warehouse if terminal else None) if company else []
    low_stock_out_count = low_stock.filter(quantity__lte=0).count() if company else 0
    low_stock_count = low_stock.filter(quantity__gt=0, quantity__lte=F('product__min_stock')).count() if company else 0

    context = {
        'terminal': terminal,
        'open_shift': open_shift,
        'terminals': terminals,
        'held_sales': held_sales,
        'categories': categories,
        'cart': cart,
        'company': company,
        'can_create_product': request.user.is_superuser or request.user.is_company_admin() or request.user.is_manager() or request.user.is_staff_user(),
        'today_summary': today_summary,
        'low_stock_products': low_stock,
        'low_stock_out_count': low_stock_out_count,
        'low_stock_count': low_stock_count,
        'is_owner': request.user.is_superuser or request.user.is_company_admin(),
    }
    return render(request, 'pos/workspace.html', context)


@login_required
def debt_ledger(request):
    company = _get_company(request)
    query = request.GET.get('q', '').strip()
    debts = []
    debt_query = Debt.objects.filter(company=company).select_related('customer', 'sale').prefetch_related('payments')
    if query:
        debt_query = debt_query.filter(Q(customer__name__icontains=query) | Q(customer__phone__icontains=query) | Q(sale__reference__icontains=query))
    with transaction.atomic():
        for debt in debt_query:
            debt.refresh_status()
            debts.append({'debt': debt, 'sale': debt.sale, 'paid': debt.paid, 'remaining': debt.remaining})
    legacy_sales = Sale.objects.filter(company=company, customer__isnull=False, payment_status__in=['unpaid', 'partial']).exclude(debt__isnull=False).select_related('customer').prefetch_related('payments')
    if query:
        legacy_sales = legacy_sales.filter(Q(customer__name__icontains=query) | Q(customer__phone__icontains=query) | Q(reference__icontains=query))
    for sale in legacy_sales:
        paid = sale.payments.aggregate(value=Sum('amount'))['value'] or Decimal('0')
        debts.append({'debt': None, 'sale': sale, 'paid': paid, 'remaining': max(Decimal('0'), sale.total - paid)})
    today = timezone.localdate()
    active = [item for item in debts if item['remaining'] > 0]
    return render(request, 'pos/debt_ledger.html', {
        'debts': active,
        'query': query,
        'total_debt': sum((item['remaining'] for item in active), Decimal('0')),
        'due_today': sum((item['remaining'] for item in active if (item['debt'].due_date if item['debt'] else item['sale'].expected_delivery_date) == today), Decimal('0')),
        'overdue_total': sum((item['remaining'] for item in active if (item['debt'].status if item['debt'] else 'overdue') == 'overdue' or (not item['debt'] and item['sale'].expected_delivery_date and item['sale'].expected_delivery_date < today)), Decimal('0')),
        'overdue_count': sum(1 for item in active if (item['debt'].status if item['debt'] else 'overdue') == 'overdue' or (not item['debt'] and item['sale'].expected_delivery_date and item['sale'].expected_delivery_date < today)),
        'today': today,
    })


@login_required
def customer_profile(request, customer_id):
    company = _get_company(request)
    customer = get_object_or_404(Customer, pk=customer_id, company=company, is_active=True)
    debts = list(Debt.objects.filter(company=company, customer=customer).select_related('sale').prefetch_related('payments'))
    with transaction.atomic():
        for debt in debts:
            debt.refresh_status()
    sales = Sale.objects.filter(company=company, customer=customer).order_by('-created_at')[:20]
    payments = DebtPayment.objects.filter(company=company, debt__customer=customer).select_related('debt', 'user')[:30]
    balance = sum((d.remaining for d in debts), Decimal('0'))
    return render(request, 'pos/customer_profile.html', {'customer': customer, 'debts': debts, 'sales': sales, 'payments': payments, 'balance': balance, 'available_credit': max(customer.credit_limit - balance, Decimal('0')) if customer.credit_limit > 0 else None})


@login_required
def api_debt_payment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    company = _get_company(request)
    try:
        data = json.loads(request.body)
        sale_id = data.get('sale_id')
        debt_id = data.get('debt_id')
        amount = Decimal(str(data.get('amount', '0')))
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'To\'lov ma\'lumotlari noto\'g\'ri'}, status=400)
    if amount <= 0:
        return JsonResponse({'success': False, 'error': 'Summa noldan katta bo\'lishi kerak'}, status=400)
    with transaction.atomic():
        debt = Debt.objects.select_for_update().filter(pk=debt_id, company=company, customer__isnull=False).select_related('sale').first() if debt_id else None
        sale = debt.sale if debt else Sale.objects.select_for_update().filter(pk=sale_id, company=company, customer__isnull=False).first()
        if sale and not debt:
            debt = Debt.objects.select_for_update().filter(sale=sale, company=company).first()
        if not sale:
            return JsonResponse({'success': False, 'error': 'Nasiya topilmadi'}, status=404)
        if not debt:
            paid_legacy = sale.payments.aggregate(value=Sum('amount'))['value'] or Decimal('0')
            debt = Debt.objects.create(company=company, sale=sale, customer=sale.customer, total=sale.total, paid=paid_legacy, due_date=sale.expected_delivery_date or timezone.localdate(), created_by=request.user)
        debt.refresh_from_db()
        if amount > debt.remaining:
            return JsonResponse({'success': False, 'error': 'To\'lov qolgan qarzdan katta'}, status=400)
        method = data.get('method', 'cash')
        if method not in dict(DebtPayment.PAYMENT_METHOD_CHOICES):
            return JsonResponse({'success': False, 'error': 'To\'lov usuli noto\'g\'ri'}, status=400)
        DebtPayment.objects.create(company=company, debt=debt, amount=amount, method=method, note=data.get('note', 'Nasiya to\'lovi'), user=request.user)
        SalePayment.objects.create(sale=sale, company=company, amount=amount, payment_method=method, notes=data.get('note', 'Nasiya to\'lovi'), created_by=request.user)
        debt.paid = sum((p.amount for p in debt.payments.all()), Decimal('0'))
        debt.refresh_status(save=False)
        debt.save(update_fields=['paid', 'status', 'updated_at'])
        Activity.log_activity('customer_debt_paid', f'Nasiya to\'lovi: {amount}', user=request.user, company=company, related_object_type='Debt', related_object_id=debt.pk)
    return JsonResponse({'success': True, 'remaining': str(debt.remaining), 'status': debt.status, 'customer_balance': str(debt.customer.outstanding_balance)})


# ============================================================
# POS API — Product Search & Barcode
# ============================================================

@login_required
def api_product_search(request):
    company = _get_company(request)
    q = request.GET.get('q', '').strip()
    terminal_id = request.session.get('pos_terminal_id')
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    page_size = 60

    products = Product.objects.filter(status='active').exclude(notes__startswith='POS quick item')
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_fk_id=category_id)
    if company:
        products = products.filter(company=company)

    popular_ids = []
    if request.GET.get('filter') == 'popular':
        popular_ids = list(
            SaleItem.objects.filter(sale__company=company)
            .values('product_id').annotate(total=Sum('quantity'))
            .order_by('-total').values_list('product_id', flat=True)[:60]
        )
        products = products.filter(pk__in=popular_ids)

    products = products.select_related('unit', 'category_fk', 'brand')
    total_products = products.count()
    products = products[(page - 1) * page_size:page * page_size]

    warehouse = None
    if terminal_id:
        terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).first() if company else POSTerminal.objects.filter(pk=terminal_id).first()
        if terminal:
            warehouse = terminal.warehouse

    results = []
    for p in products:
        available = 0
        if warehouse:
            sl = StockLevel.objects.filter(product=p, warehouse=warehouse, company=company).first()
            if sl:
                available = float(sl.quantity - sl.reserved)
            elif not StockLevel.objects.filter(product=p, company=company).exists():
                # Legacy products may have Product.quantity but no warehouse level yet.
                available = float(p.quantity)
        else:
            sls = StockLevel.objects.filter(product=p, company=company) if company else StockLevel.objects.filter(product=p)
            available = sum(float(s.quantity - s.reserved) for s in sls)

        price_result = resolve_price(product=p, company=company)

        results.append({
            'id': p.pk,
            'name': p.name,
            'sku': p.sku,
            'barcode': p.barcode,
            'price': str(price_result.final_price),
            'unit_price': str(p.price),
            'wholesale_price': str(p.wholesale_price),
            'purchase_price': str(p.purchase_price) if _is_owner(request.user) else None,
            'unit': str(p.unit) if p.unit else '',
            'unit_symbol': p.unit.symbol if p.unit else '',
            'category': p.category_fk.name if p.category_fk else '',
            'category_id': p.category_fk_id,
            'brand': p.brand.name if p.brand else '',
            'sales_count': SaleItem.objects.filter(product=p, sale__company=company).aggregate(total=Sum('quantity'))['total'] or 0,
            'available': available,
            'min_stock': p.min_stock,
            'has_variants': p.has_variants,
            'image_url': p.image.url if p.image and getattr(p.image, 'name', '') else '',
        })

    return JsonResponse({'success': True, 'products': results, 'page': page, 'has_more': page * page_size < total_products})


@login_required
def api_barcode_scan(request):
    company = _get_company(request)
    barcode = request.GET.get('code', '').strip()
    terminal_id = request.session.get('pos_terminal_id')

    if not barcode:
        return JsonResponse({'success': False, 'error': 'No barcode'})

    product = Product.objects.filter(Q(barcode=barcode), status='active').first()
    if not product:
        product = Product.objects.filter(Q(sku=barcode), status='active').first()

    if not product:
        return JsonResponse({'success': False, 'error': 'Product not found'})

    if company and product.company != company:
        return JsonResponse({'success': False, 'error': 'Product not found'})

    warehouse = None
    available = 0
    if terminal_id:
        terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).first() if company else POSTerminal.objects.filter(pk=terminal_id).first()
        if terminal:
            warehouse = terminal.warehouse

    if warehouse:
        sl = StockLevel.objects.filter(product=product, warehouse=warehouse, company=company).first()
        if sl:
            available = float(sl.quantity - sl.reserved)
    else:
        sls = StockLevel.objects.filter(product=product, company=company) if company else StockLevel.objects.filter(product=product)
        available = sum(float(s.quantity - s.reserved) for s in sls)
        if not sls.exists():
            available = float(product.quantity)

    price_result = resolve_price(product=product, company=company)

    variants = []
    if product.has_variants:
        for v in product.variants.filter(is_active=True):
            variants.append({
                'id': v.pk, 'name': v.name, 'sku': v.sku, 'barcode': v.barcode,
                'price': str(v.price), 'purchase_price': str(v.purchase_price),
            })

    return JsonResponse({
        'success': True,
        'product': {
            'id': product.pk,
            'name': product.name,
            'sku': product.sku,
            'barcode': product.barcode,
            'price': str(price_result.final_price),
            'wholesale_price': str(product.wholesale_price),
            'unit': str(product.unit) if product.unit else '',
            'unit_symbol': product.unit.symbol if product.unit else '',
            'available': available,
            'has_variants': product.has_variants,
            'variants': variants,
        }
    })


# ============================================================
# POS API — Customer Search
# ============================================================

@login_required
def api_customer_search(request):
    company = _get_company(request)
    q = request.GET.get('q', '').strip()
    if not q:
        return JsonResponse({'success': True, 'customers': []})

    customers = Customer.objects.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    if company:
        customers = customers.filter(company=company)
    customers = customers[:10]

    results = [{
        'id': c.pk, 'name': c.name, 'phone': c.phone,
        'email': c.email, 'balance': str(c.outstanding_balance),
        'credit_limit': str(c.credit_limit),
        'available_credit': str(max(c.credit_limit - c.outstanding_balance, 0)) if c.credit_limit > 0 else None,
    } for c in customers]

    return JsonResponse({'success': True, 'customers': results})


# ============================================================
# POS API — Cart Management
# ============================================================

@login_required
def api_cart_add(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})

    company = _get_company(request)
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        quantity = Decimal(str(data.get('quantity', 1)))
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Ma\'lumotlar noto\'g\'ri'}, status=400)
    if quantity <= 0:
        return JsonResponse({'success': False, 'error': 'Miqdor noldan katta bo\'lishi kerak'}, status=400)

    product_query = Product.objects.filter(pk=product_id, status='active')
    if company:
        product_query = product_query.filter(company=company)
    product = product_query.select_related('unit').first()
    if not product:
        return JsonResponse({'success': False, 'error': 'Mahsulot topilmadi'}, status=404)

    variant = None
    if variant_id:
        variant = product.variants.filter(pk=variant_id, is_active=True).first()
        if not variant:
            return JsonResponse({'success': False, 'error': 'Variant topilmadi'}, status=404)

    terminal_id = request.session.get('pos_terminal_id')
    warehouse = None
    if terminal_id:
        terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).first() if company else POSTerminal.objects.filter(pk=terminal_id).first()
        if terminal:
            warehouse = terminal.warehouse

    available = 0
    if warehouse:
        sl = StockLevel.objects.filter(product=product, warehouse=warehouse, company=company).first()
        if sl:
            available = float(sl.quantity - sl.reserved)

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})

    item_key = f"{product_id}_{variant_id or ''}"
    existing = False
    current_quantity = Decimal('0')
    for item in cart['items']:
        if item.get('key') == item_key:
            current_quantity = Decimal(str(item['quantity']))
            existing = True
            break

    if warehouse and company:
        if available < float(current_quantity + quantity):
            return JsonResponse({'success': False, 'error': f'Mavjud qoldiq yetarli emas ({available:g})'}, status=400)

    price_result = resolve_price(product=product, company=company)
    price_mode = data.get('price_mode', 'retail')
    if price_mode == 'wholesale' and not _is_owner(request.user):
        return JsonResponse({'success': False, 'error': 'Ulgurji narxni faqat egasi tanlashi mumkin'}, status=403)
    unit_price = variant.price if variant else (product.wholesale_price if price_mode == 'wholesale' and product.wholesale_price > 0 else price_result.final_price)

    if existing:
        for item in cart['items']:
            if item.get('key') == item_key:
                item['quantity'] = str(current_quantity + quantity)
                break

    if not existing:
        cart['items'].append({
            'key': item_key,
            'product_id': product_id,
            'variant_id': variant_id,
            'name': product.name,
            'sku': product.sku,
            'barcode': product.barcode,
            'unit_price': str(unit_price),
            'retail_price': str(price_result.final_price),
            'wholesale_price': str(product.wholesale_price),
            'price_mode': price_mode,
            'image_url': product.image.url if product.image and getattr(product.image, 'name', '') else '',
            'quantity': str(quantity),
            'unit': str(product.unit) if product.unit else '',
            'unit_symbol': product.unit.symbol if product.unit else '',
            'available': available,
            'discount': '0',
        })

    request.session['pos_cart'] = cart
    request.session.modified = True

    return JsonResponse({'success': True, 'cart': _calc_cart_totals(cart, company)})


@login_required
def api_cart_update(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})

    company = _get_company(request)
    try:
        data = json.loads(request.body)
        item_key = data.get('key')
        quantity = Decimal(str(data.get('quantity', 1)))
        custom_price = data.get('custom_price')
        item_discount = data.get('item_discount')
        price_mode = data.get('price_mode')
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Miqdor noto\'g\'ri'}, status=400)
    if quantity < 0:
        return JsonResponse({'success': False, 'error': 'Miqdor noto\'g\'ri'}, status=400)
    if (data.get('custom_price') is not None or price_mode == 'wholesale') and not _is_owner(request.user):
        return JsonResponse({'success': False, 'error': 'Narxni faqat egasi o\'zgartirishi mumkin'}, status=403)

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})

    terminal_id = request.session.get('pos_terminal_id')
    terminal = POSTerminal.objects.filter(
        pk=terminal_id, company=company
    ).select_related('warehouse').first() if terminal_id and company else None
    for item in cart['items']:
        if item.get('key') == item_key:
            if terminal and quantity > 0:
                available = StockLevel.objects.filter(
                    product_id=item['product_id'], warehouse=terminal.warehouse, company=company
                ).aggregate(total=Sum(F('quantity') - F('reserved')))['total'] or Decimal('0')
                if quantity > available:
                    return JsonResponse({'success': False, 'error': f'Mavjud qoldiq yetarli emas ({available:g})'}, status=400)
            if quantity <= 0:
                cart['items'].remove(item)
            else:
                item['quantity'] = str(quantity)
                if item_discount is not None:
                    item_discount = Decimal(str(item_discount))
                    gross = Decimal(str(item.get('unit_price', 0))) * quantity
                    if item_discount < 0 or item_discount > gross:
                        return JsonResponse({'success': False, 'error': 'Mahsulot chegirmasi noto\'g\'ri'}, status=400)
                    item['discount'] = str(item_discount)
                if price_mode in ('retail', 'wholesale') and not item.get('custom_price'):
                    next_price = item.get('retail_price', item.get('unit_price')) if price_mode == 'retail' else item.get('wholesale_price', '0')
                    if Decimal(str(next_price)) > 0:
                        item['unit_price'] = str(next_price)
                    item['price_mode'] = price_mode
                if custom_price is not None:
                    try:
                        custom_price = Decimal(str(custom_price))
                    except (ArithmeticError, TypeError, ValueError):
                        return JsonResponse({'success': False, 'error': 'Maxsus narx noto\'g\'ri'}, status=400)
                    if custom_price < 0:
                        return JsonResponse({'success': False, 'error': 'Maxsus narx manfiy bo\'lishi mumkin emas'}, status=400)
                    item['custom_price'] = str(custom_price)
                    item['unit_price'] = str(custom_price)
            break

    request.session['pos_cart'] = cart
    request.session.modified = True

    return JsonResponse({'success': True, 'cart': _calc_cart_totals(cart, company)})


@login_required
def api_cart_remove(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})

    company = _get_company(request)
    data = json.loads(request.body)
    item_key = data.get('key')

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})
    cart['items'] = [item for item in cart['items'] if item.get('key') != item_key]

    request.session['pos_cart'] = cart
    request.session.modified = True

    return JsonResponse({'success': True, 'cart': _calc_cart_totals(cart, company)})


@login_required
def api_cart_clear(request):
    company = _get_company(request)
    request.session['pos_cart'] = {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0}
    request.session.modified = True
    return JsonResponse({'success': True, 'cart': _calc_cart_totals(request.session['pos_cart'], company)})


@login_required
def api_cart_customer(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    company = _get_company(request)
    data = json.loads(request.body)
    customer_id = data.get('customer_id')

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})
    cart['customer_id'] = customer_id
    request.session['pos_cart'] = cart
    request.session.modified = True

    customer_name = ''
    if customer_id:
        c = Customer.objects.filter(pk=customer_id, company=company, is_active=True).first()
        if not c:
            return JsonResponse({'success': False, 'error': 'Mijoz topilmadi'}, status=404)
        customer_name = c.name

    return JsonResponse({'success': True, 'customer_name': customer_name, 'cart': _calc_cart_totals(cart, company)})


@login_required
def api_customer_create(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    company = _get_company(request)
    if not company:
        return JsonResponse({'success': False, 'error': 'Kompaniya topilmadi'}, status=400)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ma\'lumotlar noto\'g\'ri'}, status=400)
    name = str(data.get('name', '')).strip()
    phone = str(data.get('phone', '')).strip()
    if len(name) < 2 or not phone:
        return JsonResponse({'success': False, 'error': 'Ism va telefon raqami kerak'}, status=400)
    customer = Customer.objects.create(
        company=company, name=name, phone=phone,
        payment_terms='credit' if data.get('credit') else 'cod',
    )
    return JsonResponse({'success': True, 'customer': {
        'id': customer.pk, 'name': customer.name, 'phone': customer.phone, 'balance': '0'
    }})


@login_required
def api_cart_discount(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    company = _get_company(request)
    data = json.loads(request.body)
    try:
        discount = Decimal(str(data.get('discount', 0)))
    except (ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Chegirma noto\'g\'ri'}, status=400)
    if discount < 0:
        return JsonResponse({'success': False, 'error': 'Chegirma manfiy bo\'lishi mumkin emas'}, status=400)

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})
    subtotal = sum(
        Decimal(str(item.get('unit_price', 0))) * Decimal(str(item.get('quantity', 0)))
        - Decimal(str(item.get('discount', 0)))
        for item in cart.get('items', [])
    )
    if discount > subtotal:
        return JsonResponse({'success': False, 'error': 'Chegirma jami summadan katta bo\'lishi mumkin emas'}, status=400)
    cart['discount_amount'] = str(discount)
    cart['discount_mode'] = data.get('mode', 'amount')
    cart['discount_value'] = str(data.get('value', discount))
    cart['discount_reason'] = data.get('reason', '')
    request.session['pos_cart'] = cart
    request.session.modified = True

    return JsonResponse({'success': True, 'cart': _calc_cart_totals(cart, company)})


# ============================================================
# POS API — Quick product creation
# ============================================================

@login_required
def api_product_create(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    company = _get_company(request)
    if not company or not _can_manage_stock(request.user):
        return JsonResponse({'success': False, 'error': 'Mahsulot yaratish huquqi yo\'q'}, status=403)

    try:
        if request.content_type.startswith('multipart/form-data'):
            data = request.POST
            photo = request.FILES.get('image')
        else:
            data = json.loads(request.body)
            photo = None
        name = str(data.get('name', '')).strip()
        sku = str(data.get('sku', '')).strip()
        price = Decimal(str(data.get('price', '0')))
        purchase_price = Decimal(str(data.get('purchase_price', '0') or '0'))
        stock = int(data.get('stock', 0) or 0)
        min_stock = int(data.get('min_stock', 5) or 5)
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Ma\'lumotlar noto\'g\'ri'}, status=400)

    if not name or not sku or price < 0 or purchase_price < 0 or stock < 0 or min_stock < 0:
        return JsonResponse({'success': False, 'error': 'Nom, SKU va narxni to\'g\'ri kiriting'}, status=400)
    if Product.objects.filter(sku=sku).exists():
        return JsonResponse({'success': False, 'error': 'Bu SKU allaqachon mavjud'}, status=400)

    from products.models import Category, Unit
    category = Category.objects.filter(
        pk=data.get('category_id'), is_active=True
    ).filter(Q(company=company) | Q(company__isnull=True)).first() if data.get('category_id') else None
    unit = Unit.objects.filter(pk=data.get('unit_id'), is_active=True).first() if data.get('unit_id') else None

    terminal_id = request.session.get('pos_terminal_id')
    terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).select_related('warehouse').first() if terminal_id else None
    stock_warehouse = terminal.warehouse if terminal else StockEngine.default_warehouse(company)
    try:
        with transaction.atomic():
            product = Product.objects.create(
                company=company, name=name, sku=sku,
                barcode=str(data.get('barcode', '')).strip() or None,
                price=price, purchase_price=purchase_price, category_fk=category,
                unit=unit, status='active', quantity=stock, min_stock=min_stock,
                image=photo,
            )
            if stock_warehouse:
                StockLevel.objects.update_or_create(
                    company=company, product=product, warehouse=stock_warehouse,
                    defaults={'quantity': stock, 'reserved': 0},
                )
    except (IntegrityError, ValueError):
        return JsonResponse({'success': False, 'error': 'SKU yoki mahsulot ma\'lumotlari takrorlangan'}, status=400)

    return JsonResponse({
        'success': True,
        'product': {
            'id': product.pk,
            'name': product.name,
            'sku': product.sku,
            'barcode': product.barcode,
            'price': str(product.price),
            'available': stock,
            'min_stock': min_stock,
            'unit_symbol': product.unit.symbol if product.unit else '',
            'category': product.category_fk.name if product.category_fk else '',
            'image_url': product.image.url if product.image else '',
        },
    })


@login_required
def api_quick_item(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    company = _get_company(request)
    if not _can_manage_stock(request.user):
        return JsonResponse({'success': False, 'error': 'Mahsulot va qoldiqni faqat egasi yoki menejer boshqaradi'}, status=403)
    if not company:
        return JsonResponse({'success': False, 'error': 'Kompaniya topilmadi'}, status=400)
    try:
        data = json.loads(request.body)
        name = str(data.get('name', '')).strip()
        price = Decimal(str(data.get('price', '0')))
        quantity = Decimal(str(data.get('quantity', '1')))
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Tezkor mahsulot ma\'lumotlari noto\'g\'ri'}, status=400)
    if not name or price < 0 or quantity <= 0:
        return JsonResponse({'success': False, 'error': 'Nom, narx va miqdorni kiriting'}, status=400)
    terminal_id = request.session.get('pos_terminal_id')
    terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).select_related('warehouse').first() if terminal_id else None
    sku = f"QUICK-{uuid.uuid4().hex[:10].upper()}"
    try:
        with transaction.atomic():
            product = Product.objects.create(
                company=company, name=name, sku=sku, price=price,
                purchase_price=price, quantity=int(quantity), status='active',
                notes='POS quick item; hidden from standard catalog' if not data.get('save_to_catalog') else '',
            )
            if terminal:
                StockLevel.objects.update_or_create(
                    company=company, product=product, warehouse=terminal.warehouse,
                    defaults={'quantity': int(quantity), 'reserved': 0},
                )
        return JsonResponse({'success': True, 'product': {'id': product.pk, 'name': product.name, 'sku': product.sku, 'price': str(product.price), 'available': int(quantity), 'unit_symbol': 'dona', 'category': 'Tezkor mahsulot', 'category_id': None, 'image_url': ''}})
    except IntegrityError:
        return JsonResponse({'success': False, 'error': 'Tezkor mahsulot saqlanmadi'}, status=400)


@login_required
def api_product_import(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    company = _get_company(request)
    if not _can_manage_stock(request.user):
        return JsonResponse({'success': False, 'error': 'Qoldiqni faqat egasi yoki menejer boshqaradi'}, status=403)
    upload = request.FILES.get('file')
    if not company or not upload:
        return JsonResponse({'success': False, 'error': 'CSV fayl tanlang'}, status=400)
    try:
        rows = list(csv.DictReader(io.TextIOWrapper(upload.file, encoding='utf-8-sig')))
    except (UnicodeDecodeError, csv.Error):
        return JsonResponse({'success': False, 'error': 'CSV kodirovkasini o\'qib bo\'lmadi'}, status=400)
    required = {'name', 'sell_price'}
    if not rows or not required.issubset({key.strip() for key in rows[0].keys()}):
        return JsonResponse({'success': False, 'error': 'Ustunlar kerak: name,sell_price,buy_price,stock,min_stock,category,sku,barcode'}, status=400)
    errors = []
    prepared = []
    for row_number, row in enumerate(rows, 2):
        try:
            name = str(row.get('name', '')).strip()
            price = Decimal(str(row.get('sell_price', '0') or '0'))
            purchase = Decimal(str(row.get('buy_price', '0') or '0'))
            stock = int(row.get('stock', 0) or 0)
            min_stock = int(row.get('min_stock', 5) or 5)
            sku = str(row.get('sku', '')).strip() or f"IMP-{uuid.uuid4().hex[:10].upper()}"
            if not name or price < 0 or purchase < 0 or stock < 0 or min_stock < 0:
                raise ValueError('nom, narx yoki qoldiq noto\'g\'ri')
            if Product.objects.filter(sku=sku).exists() or any(item['sku'] == sku for item in prepared):
                raise ValueError('SKU takrorlangan')
            category_name = str(row.get('category', '')).strip()
            category = Category.objects.filter(company=company, name=category_name, is_active=True).first() if category_name else None
            prepared.append({'name': name, 'price': price, 'purchase': purchase, 'stock': stock, 'min_stock': min_stock, 'sku': sku, 'barcode': str(row.get('barcode', '')).strip() or None, 'category': category})
        except (ArithmeticError, TypeError, ValueError) as exc:
            errors.append({'row': row_number, 'error': str(exc)})
    if errors:
        return JsonResponse({'success': False, 'created': 0, 'errors': errors}, status=400)
    with transaction.atomic():
        terminal_id = request.session.get('pos_terminal_id')
        terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).select_related('warehouse').first() if terminal_id else None
        for item in prepared:
            product = Product.objects.create(company=company, name=item['name'], sku=item['sku'], barcode=item['barcode'], price=item['price'], purchase_price=item['purchase'], quantity=item['stock'], min_stock=item['min_stock'], category_fk=item['category'], status='active')
            if terminal and item['stock']:
                StockLevel.objects.create(company=company, product=product, warehouse=terminal.warehouse, quantity=item['stock'])
    return JsonResponse({'success': True, 'created': len(prepared), 'errors': []})


# ============================================================
# POS API — Checkout
# ============================================================

@login_required
def api_checkout(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})

    company = _get_company(request)
    data = json.loads(request.body)

    terminal_id = data.get('terminal_id') or request.session.get('pos_terminal_id')
    shift_id = data.get('shift_id')
    payment_method = data.get('payment_method', 'cash')
    payments = data.get('payments', [])
    idempotency_key = str(data.get('idempotency_key', '')).strip()[:80]
    amount_paid = Decimal(str(data.get('amount_paid', 0)))
    credit_sale = bool(data.get('credit_sale'))
    due_date = data.get('due_date') or None
    credit_note = str(data.get('credit_note', '')).strip()[:2000]

    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})

    if idempotency_key:
        existing_sale = Sale.objects.filter(company=company, idempotency_key=idempotency_key).select_related('pos_receipt').first()
        if existing_sale:
            receipt = getattr(existing_sale, 'pos_receipt', None)
            return JsonResponse({'success': True, 'duplicate': True, 'sale_id': existing_sale.pk, 'receipt_id': receipt.pk if receipt else None, 'receipt_number': receipt.receipt_number if receipt else existing_sale.reference, 'total': str(existing_sale.total), 'amount_paid': str(existing_sale.total_paid_amount), 'change': '0'})

    if not cart.get('items'):
        return JsonResponse({'success': False, 'error': 'Cart is empty'})

    terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).first() if terminal_id and company else None
    shift = CashShift.objects.filter(
        pk=shift_id, company=company, cashier=request.user,
        terminal=terminal, status='open'
    ).first() if shift_id and company else None

    if not shift:
        return JsonResponse({'success': False, 'error': 'Avval smenani oching. Sotuvni boshlash uchun ochiq smena kerak.'}, status=400)

    allowed_methods = {'cash', 'card', 'transfer', 'online', 'other', 'mixed'}
    if payment_method not in allowed_methods:
        return JsonResponse({'success': False, 'error': 'To\'lov usuli noto\'g\'ri'}, status=400)
    if not isinstance(payments, list):
        return JsonResponse({'success': False, 'error': 'To\'lovlar ro\'yxati noto\'g\'ri'}, status=400)

    warehouse = terminal.warehouse if terminal else None

    # Rebuild sellable prices from the database. Browser cart values are only
    # a display snapshot and must never determine the recorded sale total.
    validated_items = []
    for item in cart['items']:
        product = Product.objects.filter(
            pk=item.get('product_id'), company=company, status='active'
        ).first()
        if not product:
            return JsonResponse({'success': False, 'error': 'Savatdagi mahsulot topilmadi'}, status=400)
        variant = None
        if item.get('variant_id'):
            variant = ProductVariant.objects.filter(
                pk=item['variant_id'], product=product, is_active=True
            ).first()
            if not variant:
                return JsonResponse({'success': False, 'error': 'Savatdagi variant topilmadi'}, status=400)
        try:
            qty = Decimal(str(item.get('quantity', 0)))
            line_discount = Decimal(str(item.get('discount', 0)))
        except (ArithmeticError, TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Savatdagi miqdor noto\'g\'ri'}, status=400)
        base_price = variant.price if variant else (product.wholesale_price if item.get('price_mode') == 'wholesale' and product.wholesale_price > 0 else resolve_price(product=product, company=company).final_price)
        try:
            custom_price = Decimal(str(item.get('custom_price'))) if item.get('custom_price') is not None else None
        except (ArithmeticError, TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Maxsus narx noto\'g\'ri'}, status=400)
        if custom_price is not None and custom_price < 0:
            return JsonResponse({'success': False, 'error': 'Maxsus narx noto\'g\'ri'}, status=400)
        unit_price = custom_price if custom_price is not None else base_price
        if qty <= 0 or line_discount < 0 or line_discount > unit_price * qty:
            return JsonResponse({'success': False, 'error': 'Savatdagi narx yoki chegirma noto\'g\'ri'}, status=400)
        normalized = dict(item)
        normalized['unit_price'] = str(unit_price)
        normalized['discount'] = str(line_discount)
        validated_items.append(normalized)
    cart['items'] = validated_items

    totals = _calc_cart_totals(cart, company)
    total = Decimal(totals['total'])
    subtotal = Decimal(totals['subtotal'])
    discount_amount = Decimal(totals['discount_amount'])
    tax_amount = Decimal(totals['tax_amount'])

    total_paid = Decimal('0')
    if payments:
        for p in payments:
            if p.get('method') not in allowed_methods:
                return JsonResponse({'success': False, 'error': 'To\'lov usuli noto\'g\'ri'}, status=400)
            payment_amount = Decimal(str(p.get('amount', 0)))
            if payment_amount < 0:
                return JsonResponse({'success': False, 'error': 'To\'lov summasi noto\'g\'ri'}, status=400)
            total_paid += payment_amount
    else:
        total_paid = amount_paid

    if amount_paid < 0 or (not credit_sale and total_paid < total):
        return JsonResponse({'success': False, 'error': 'To\'lov summasi yetarli emas'}, status=400)

    change = total_paid - total
    if change < 0:
        change = Decimal('0')

    payment_status = 'unpaid'
    if total_paid >= total:
        payment_status = 'paid'
    elif total_paid > 0:
        payment_status = 'partial'

    customer_id = cart.get('customer_id')
    customer = None
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id, company=company, is_active=True).first()
        if not customer:
            return JsonResponse({'success': False, 'error': 'Mijoz topilmadi'}, status=400)

    parsed_due_date = None
    if credit_sale:
        if not customer:
            return JsonResponse({'success': False, 'error': 'Nasiya uchun mijozni tanlang'}, status=400)
        if not due_date:
            return JsonResponse({'success': False, 'error': 'Qaytarish sanasini kiriting'}, status=400)
        try:
            from datetime import date
            parsed_due_date = date.fromisoformat(due_date)
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Qaytarish sanasi noto\'g\'ri'}, status=400)
        if parsed_due_date < timezone.now().date():
            return JsonResponse({'success': False, 'error': 'Qaytarish sanasi bugundan oldin bo\'lishi mumkin emas'}, status=400)
        if total_paid > total:
            return JsonResponse({'success': False, 'error': 'Oldindan to\'lov jamidan katta'}, status=400)
        current_credit = customer.outstanding_balance
        new_credit = total - total_paid
        if customer.credit_limit > 0 and current_credit + new_credit > customer.credit_limit:
            return JsonResponse({'success': False, 'error': f'Kredit limiti oshadi. Mavjud qarz: {current_credit:.2f}, limit: {customer.credit_limit:.2f}'}, status=400)

    with transaction.atomic():
        receipt_number = _next_receipt_number(company)

        receipt = POSReceipt.objects.create(
            company=company,
            terminal=terminal,
            shift=shift,
            receipt_number=receipt_number,
            customer=customer,
            warehouse=warehouse,
            subtotal=subtotal,
            tax_rate=getattr(company, 'pos_tax_rate', Decimal('0')),
            tax_amount=tax_amount,
            discount_amount=discount_amount,
            total=total,
            amount_paid=total_paid,
            change=change,
            payment_method=payment_method if len(payments) <= 1 else 'mixed',
            coupon_code=cart.get('coupon_code', ''),
            status='completed',
            completed_at=timezone.now(),
            created_by=request.user,
        )

        for item in cart['items']:
            product = Product.objects.filter(
                pk=item['product_id'], company=company, status='active'
            ).first()
            if not product:
                return JsonResponse({'success': False, 'error': 'Savatdagi mahsulot topilmadi'}, status=400)
            variant = None
            if item.get('variant_id'):
                variant = ProductVariant.objects.filter(
                    pk=item['variant_id'], product=product, is_active=True
                ).first()
                if not variant:
                    return JsonResponse({'success': False, 'error': 'Savatdagi variant topilmadi'}, status=400)

            qty = Decimal(item['quantity'])
            if qty <= 0:
                return JsonResponse({'success': False, 'error': 'Savatdagi miqdor noto\'g\'ri'}, status=400)
            base_price = variant.price if variant else (product.wholesale_price if item.get('price_mode') == 'wholesale' and product.wholesale_price > 0 else resolve_price(product=product, company=company).final_price)
            custom_price = Decimal(str(item['custom_price'])) if item.get('custom_price') is not None else None
            unit_price = custom_price if custom_price is not None else base_price
            discount = Decimal(item.get('discount', 0))
            line_total = (unit_price * qty) - discount

            stock_level = StockLevel.objects.select_for_update().filter(
                product=product, warehouse=warehouse, company=company
            ).first()
            available = (stock_level.quantity - stock_level.reserved) if stock_level else Decimal('0')
            if available < qty:
                return JsonResponse({'success': False, 'error': f'{product.name}: qoldiq yetarli emas'}, status=400)

            POSReceiptItem.objects.create(
                receipt=receipt,
                product=product,
                variant=variant,
                quantity=qty,
                unit_price=unit_price,
                discount=discount,
                line_total=line_total,
            )

            if warehouse and company:
                StockEngine.process_stock_change(
                    product=product,
                    warehouse=warehouse,
                    company=company,
                    direction='OUT',
                    movement_type='sale',
                    quantity=qty,
                    user=request.user,
                    reference_type='POSReceipt',
                    reference_id=receipt.pk,
                    reference_number=receipt.receipt_number,
                    reason=f"POS Sale: {product.name} x{qty}",
                )

        sale = Sale.objects.create(
            company=company,
            reference=receipt.receipt_number,
            idempotency_key=idempotency_key or None,
            customer=customer,
            warehouse=warehouse,
            total=total,
            discount=discount_amount,
            tax=tax_amount,
            payment_status=payment_status,
            payment_terms='credit' if credit_sale else 'cod',
            expected_delivery_date=parsed_due_date,
            currency='UZS',
            status='completed',
            notes=credit_note,
            created_by=request.user,
        )

        for item in receipt.items.all():
            SaleItem.objects.create(
                sale=sale,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount,
                total=item.line_total,
            )

        if payments:
            for p in payments:
                SalePayment.objects.create(
                    sale=sale,
                    company=company,
                    amount=Decimal(str(p.get('amount', 0))),
                    payment_method=p.get('method', 'cash'),
                    created_by=request.user,
                )
        else:
            SalePayment.objects.create(
                sale=sale,
                company=company,
                amount=total_paid,
                payment_method=payment_method,
                created_by=request.user,
            )

        if credit_sale:
            debt = Debt.objects.create(
                company=company, sale=sale, customer=customer, total=total,
                paid=total_paid, due_date=parsed_due_date, note=credit_note,
                created_by=request.user,
            )
            debt.refresh_status(save=True)
            for payment in payments:
                payment_amount = Decimal(str(payment.get('amount', 0)))
                if payment_amount > 0:
                    DebtPayment.objects.create(
                        company=company, debt=debt, amount=payment_amount,
                        method=payment.get('method', 'cash'), user=request.user,
                        note='Boshlang\'ich to\'lov',
                    )
            if not payments and total_paid > 0:
                DebtPayment.objects.create(
                    company=company, debt=debt, amount=total_paid,
                    method=payment_method, user=request.user,
                    note='Boshlang\'ich to\'lov',
                )
            Activity.log_activity('customer_debt_created', f'POS nasiya yaratildi: {debt.pk}', user=request.user, company=company, related_object_type='Debt', related_object_id=debt.pk)

        receipt.sale = sale
        receipt.save(update_fields=['sale'])

        if company:
            account = FinancialAccount.objects.filter(company=company, is_active=True).first()
            FinancialTransaction.objects.create(
                company=company,
                date=timezone.now().date(),
                txn_type='sale',
                direction='income',
                amount=total,
                account=account,
                category='POS Sale',
                customer=customer,
                reference_type='POSReceipt',
                reference_id=receipt.pk,
                reference_number=receipt.receipt_number,
                payment_method=payment_method,
                description=f"POS Sale {receipt.receipt_number}",
                created_by=request.user,
            )

        if shift:
            cash_amount = Decimal('0')
            if payments:
                for p in payments:
                    if p.get('method') == 'cash':
                        cash_amount += Decimal(str(p.get('amount', 0)))
            elif payment_method == 'cash':
                cash_amount = total_paid

            if cash_amount > 0:
                CashMovement.objects.create(
                    company=company,
                    shift=shift,
                    movement_type='sale_cash',
                    amount=cash_amount,
                    reference_type='POSReceipt',
                    reference_id=receipt.pk,
                    reference_number=receipt.receipt_number,
                    description=f"Cash from sale {receipt.receipt_number}",
                    created_by=request.user,
                )

        Activity.log_activity(
            'product_added',
            f"POS sale completed: {receipt.receipt_number}, Total: {total}",
            user=request.user, company=company,
            related_object_type='POSReceipt', related_object_id=receipt.pk,
        )

    request.session['pos_cart'] = {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0}
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'sale_id': sale.pk,
        'receipt_id': receipt.pk,
        'receipt_number': receipt.receipt_number,
        'total': str(total),
        'amount_paid': str(total_paid),
        'change': str(change),
        'payment_method': receipt.payment_method,
    })


# ============================================================
# POS API — Hold/Resume Sale
# ============================================================

@login_required
def api_hold_sale(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    company = _get_company(request)
    data = json.loads(request.body) if request.body else {}
    terminal_id = data.get('terminal_id') or request.session.get('pos_terminal_id')
    cart = request.session.get('pos_cart', {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0})

    if not cart.get('items'):
        return JsonResponse({'success': False, 'error': 'Cart is empty'})

    terminal = POSTerminal.objects.filter(pk=terminal_id, company=company).first() if terminal_id else None

    totals = _calc_cart_totals(cart, company)
    ticket_count = HeldSale.objects.filter(terminal=terminal, cashier=request.user).count() if terminal else 0

    held = HeldSale.objects.create(
        company=company,
        terminal=terminal,
        cashier=request.user,
        customer_id=cart.get('customer_id'),
        ticket_number=f"HOLD-{ticket_count + 1:04d}",
        name=str(data.get('name', '')).strip()[:120],
        cart_data=cart,
        subtotal=Decimal(totals['subtotal']),
        discount_amount=Decimal(totals['discount_amount']),
        total=Decimal(totals['total']),
        coupon_code=cart.get('coupon_code', ''),
    )

    request.session['pos_cart'] = {'items': [], 'customer_id': None, 'coupon_code': '', 'discount_amount': 0}
    request.session.modified = True

    return JsonResponse({'success': True, 'ticket_number': held.ticket_number})


@login_required
def api_resume_sale(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    company = _get_company(request)
    data = json.loads(request.body)
    held_id = data.get('held_id')

    held = get_object_or_404(HeldSale, pk=held_id, cashier=request.user, company=company)

    request.session['pos_cart'] = held.cart_data
    request.session.modified = True

    held.delete()

    return JsonResponse({'success': True, 'cart': _calc_cart_totals(held.cart_data, company)})


@login_required
def api_delete_held(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    data = json.loads(request.body)
    held_id = data.get('held_id')
    held = get_object_or_404(HeldSale, pk=held_id, cashier=request.user, company=_get_company(request))
    held.delete()
    return JsonResponse({'success': True})


# ============================================================
# POS API — Shift Management
# ============================================================

@login_required
def api_open_shift(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    company = _get_company(request)
    data = json.loads(request.body)
    terminal_id = data.get('terminal_id')
    try:
        opening_amount = Decimal(str(data.get('opening_amount', 0)))
    except (ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Boshlang\'ich summa noto\'g\'ri'}, status=400)
    if opening_amount < 0:
        return JsonResponse({'success': False, 'error': 'Boshlang\'ich summa manfiy bo\'lishi mumkin emas'}, status=400)

    terminal = get_object_or_404(POSTerminal, pk=terminal_id, company=company)

    with transaction.atomic():
        CashShift.objects.filter(terminal=terminal, cashier=request.user, status='open').update(status='closed', closed_at=timezone.now())
        shift = CashShift.objects.create(company=company, terminal=terminal, cashier=request.user, shift_number=_next_shift_number(company), opening_amount=opening_amount, notes=str(data.get('notes', '')), created_by=request.user)
        CashMovement.objects.create(company=company, shift=shift, movement_type='opening', amount=opening_amount, description='Opening cash', created_by=request.user)

    Activity.log_activity('product_added', f"Shift {shift.shift_number} opened with {opening_amount}",
        user=request.user, company=company, related_object_type='CashShift', related_object_id=shift.pk)

    return JsonResponse({'success': True, 'shift_id': shift.pk, 'shift_number': shift.shift_number})


@login_required
def api_close_shift(request):
    if request.method != 'POST':
        return JsonResponse({'success': False})

    company = _get_company(request)
    data = json.loads(request.body)
    shift_id = data.get('shift_id')
    try:
        closing_amount = Decimal(str(data.get('closing_amount', 0)))
    except (ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Yopilish summasi noto\'g\'ri'}, status=400)
    if closing_amount < 0:
        return JsonResponse({'success': False, 'error': 'Yopilish summasi manfiy bo\'lishi mumkin emas'}, status=400)

    shift = get_object_or_404(CashShift, pk=shift_id, company=company, cashier=request.user, status='open')

    with transaction.atomic():
        shift = CashShift.objects.select_for_update().get(pk=shift.pk)
        summary = _shift_summary(shift)
        expected = summary['expected_cash']
        shift.closing_amount = closing_amount
        shift.expected_amount = expected
        shift.difference = closing_amount - expected
        shift.status = 'closed'
        shift.closed_at = timezone.now()
        shift.save(update_fields=['closing_amount', 'expected_amount', 'difference', 'status', 'closed_at'])
        CashMovement.objects.create(company=company, shift=shift, movement_type='closing', amount=closing_amount, description='Closing cash', created_by=request.user)

    Activity.log_activity('product_updated', f"Shift {shift.shift_number} closed. Difference: {shift.difference}",
        user=request.user, company=company, related_object_type='CashShift', related_object_id=shift.pk)

    return JsonResponse({
        'success': True,
        'expected': str(expected),
        'closing': str(closing_amount),
        'difference': str(shift.difference),
        'card': str(summary['card']), 'transfer': str(summary['transfer']), 'credit': str(summary['credit']), 'expenses': str(summary['expenses']),
    })


@login_required
def api_shift_summary(request):
    company = _get_company(request)
    shift = get_object_or_404(CashShift, pk=request.GET.get('shift_id'), company=company, cashier=request.user, status='open')
    summary = _shift_summary(shift)
    return JsonResponse({'success': True, **{key: str(value) for key, value in summary.items()}})


@login_required
def api_shift_expense(request):
    if request.method != 'POST': return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    company = _get_company(request)
    try:
        data = json.loads(request.body)
        amount = Decimal(str(data.get('amount', '0')))
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Xarajat summasi noto\'g\'ri'}, status=400)
    if amount <= 0: return JsonResponse({'success': False, 'error': 'Summa noldan katta bo\'lishi kerak'}, status=400)
    shift = get_object_or_404(CashShift, pk=data.get('shift_id'), company=company, cashier=request.user, status='open')
    method = data.get('method', 'cash')
    if method not in {'cash', 'card', 'transfer', 'other'}: return JsonResponse({'success': False, 'error': 'To\'lov usuli noto\'g\'ri'}, status=400)
    with transaction.atomic():
        txn = FinancialTransaction.objects.create(company=company, date=timezone.localdate(), txn_type='expense', direction='expense', amount=amount, category=str(data.get('category', 'Boshqa')), payment_method=method, reference_type='CashShift', reference_id=shift.pk, description=str(data.get('note', '')), status='completed', created_by=request.user)
        if method == 'cash': CashMovement.objects.create(company=company, shift=shift, movement_type='cash_out', amount=amount, reference_type='FinancialTransaction', reference_id=txn.pk, description=str(data.get('note', 'Xarajat')), created_by=request.user)
    return JsonResponse({'success': True, 'expense_id': txn.pk, 'amount': str(amount)})


@login_required
def api_low_stock(request):
    company = _get_company(request)
    terminal = POSTerminal.objects.filter(pk=request.session.get('pos_terminal_id'), company=company).select_related('warehouse').first() if company else None
    products = _low_stock_products(company, terminal.warehouse if terminal else None) if company else []
    return JsonResponse({'success': True, 'count': len(products), 'products': [{'id': p.product_id, 'name': p.product.name, 'sku': p.product.sku, 'available': str(p.quantity - p.reserved), 'min_stock': p.product.min_stock, 'warehouse': p.warehouse.name} for p in products]})


@login_required
def api_low_stock_export(request):
    company = _get_company(request)
    products = _low_stock_products(company) if company else []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'sku', 'available', 'min_stock', 'warehouse'])
    for level in products: writer.writerow([level.product.name, level.product.sku, level.quantity - level.reserved, level.product.min_stock, level.warehouse.name])
    response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="buyurtma-royxati.csv"'
    return response


@login_required
def api_stock_in(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    if not _can_manage_stock(request.user):
        return JsonResponse({'success': False, 'error': 'Qoldiqni faqat egasi yoki menejer boshqaradi'}, status=403)
    company = _get_company(request)
    try:
        data = json.loads(request.body)
        quantity = Decimal(str(data.get('quantity', '0')))
        buy_price = Decimal(str(data.get('buy_price'))) if data.get('buy_price') not in (None, '') else None
        sell_price = Decimal(str(data.get('sell_price'))) if data.get('sell_price') not in (None, '') else None
    except (json.JSONDecodeError, ArithmeticError, TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Kirim ma\'lumotlari noto\'g\'ri'}, status=400)
    if quantity <= 0 or quantity != quantity.to_integral_value():
        return JsonResponse({'success': False, 'error': 'Miqdor musbat butun son bo\'lishi kerak'}, status=400)
    terminal = POSTerminal.objects.filter(pk=request.session.get('pos_terminal_id'), company=company).select_related('warehouse').first()
    if not terminal:
        return JsonResponse({'success': False, 'error': 'Avval terminalni tanlang'}, status=400)
    product = Product.objects.filter(pk=data.get('product_id'), company=company, status='active').first()
    if not product:
        return JsonResponse({'success': False, 'error': 'Mahsulot topilmadi'}, status=404)
    with transaction.atomic():
        if buy_price is not None:
            product.purchase_price = buy_price
        if sell_price is not None:
            product.price = sell_price
        if buy_price is not None or sell_price is not None:
            product.save(update_fields=['purchase_price', 'price', 'updated_at'])
        StockEngine.process_stock_change(product=product, warehouse=terminal.warehouse, company=company, direction='IN', movement_type='purchase', quantity=quantity, user=request.user, reference_type='POSStockIn', reference_id=product.pk, reference_number=f'IN-{timezone.now():%Y%m%d%H%M%S}', reason=str(data.get('note', 'POS kirim')))
        Activity.log_activity('stock_in', f'POS kirim: {product.name} x{quantity}', user=request.user, company=company, related_object_type='Product', related_object_id=product.pk)
    level = StockLevel.objects.filter(product=product, warehouse=terminal.warehouse, company=company).first()
    return JsonResponse({'success': True, 'product_id': product.pk, 'available': str(level.quantity - level.reserved if level else 0), 'movement_count': StockLevel.objects.filter(product=product, company=company).count()})


# ============================================================
# POS MANAGEMENT — Dashboard
# ============================================================

@login_required
@never_cache
def pos_dashboard(request):
    company = _get_company(request)
    if not company and not request.user.is_superuser:
        return redirect('login')

    today = timezone.now().date()
    month_start = today.replace(day=1)

    if company:
        receipts = POSReceipt.objects.filter(company=company)
        shifts = CashShift.objects.filter(company=company)
    else:
        receipts = POSReceipt.objects.all()
        shifts = CashShift.objects.all()

    today_receipts = receipts.filter(created_at__date=today)
    completed = today_receipts.filter(status='completed')

    context = {
        'receipts_today': completed.count(),
        'sales_today': completed.aggregate(t=Sum('total'))['t'] or 0,
        'receipts_month': receipts.filter(created_at__date__gte=month_start, status='completed').count(),
        'sales_month': receipts.filter(created_at__date__gte=month_start, status='completed').aggregate(t=Sum('total'))['t'] or 0,
        'open_shifts': shifts.filter(status='open').count(),
        'active_terminals': POSTerminal.objects.filter(company=company, is_active=True).count() if company else POSTerminal.objects.filter(is_active=True).count(),
        'recent_receipts': receipts.select_related('terminal', 'customer').order_by('-created_at')[:10],
        'payment_breakdown': completed.values('payment_method').annotate(total=Sum('total'), count=Count('id')),
        'company': company,
    }
    return render(request, 'pos/pos_dashboard.html', context)


# ============================================================
# POS MANAGEMENT — Terminal CRUD
# ============================================================

@login_required
@never_cache
def terminal_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        terminals = POSTerminal.objects.filter(company=company).select_related('warehouse')
    else:
        terminals = POSTerminal.objects.select_related('warehouse').all()

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    warehouse_filter = request.GET.get('warehouse', '')

    if q:
        terminals = terminals.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(serial_number__icontains=q)
        )
    if status_filter:
        terminals = terminals.filter(status=status_filter)
    if warehouse_filter:
        terminals = terminals.filter(warehouse_id=warehouse_filter)

    terminals = terminals.order_by('name')
    paginator = Paginator(terminals, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'warehouses': warehouses,
        'q': q,
        'status_filter': status_filter,
        'warehouse_filter': warehouse_filter,
        'status_choices': POSTerminal.TERMINAL_STATUS_CHOICES,
        'total_count': paginator.count,
    }
    return render(request, 'pos/terminal_list.html', context)


@login_required
@never_cache
def terminal_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    if request.method == 'POST':
        form = POSTerminalForm(request.POST)
        if form.is_valid():
            terminal = form.save(commit=False)
            terminal.company = company
            terminal.save()
            Activity.log_activity(
                'product_added',
                f"POS terminal {terminal.name} created",
                user=request.user, company=company,
                related_object_type='POSTerminal', related_object_id=terminal.pk,
            )
            messages.success(request, get_translation('pos_terminal_created', lang))
            return redirect('pos:terminal_list')
    else:
        form = POSTerminalForm()

    return render(request, 'pos/terminal_form.html', {
        'form': form,
        'warehouses': warehouses,
    })


@login_required
@never_cache
def terminal_detail(request, pk):
    company = _get_company(request)
    if company:
        terminal = get_object_or_404(POSTerminal, pk=pk, company=company)
    else:
        terminal = get_object_or_404(POSTerminal, pk=pk)

    shifts = terminal.shifts.all().order_by('-opened_at')[:10]
    recent_receipts = terminal.receipts.all().order_by('-created_at')[:10]

    context = {
        'terminal': terminal,
        'shifts': shifts,
        'recent_receipts': recent_receipts,
    }
    return render(request, 'pos/terminal_detail.html', context)


@login_required
@never_cache
def terminal_update(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        terminal = get_object_or_404(POSTerminal, pk=pk, company=company)
    else:
        terminal = get_object_or_404(POSTerminal, pk=pk)

    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    if request.method == 'POST':
        form = POSTerminalForm(request.POST, instance=terminal)
        if form.is_valid():
            form.save()
            Activity.log_activity(
                'product_updated',
                f"POS terminal {terminal.name} updated",
                user=request.user, company=company,
                related_object_type='POSTerminal', related_object_id=terminal.pk,
            )
            messages.success(request, get_translation('pos_terminal_updated', lang))
            return redirect('pos:terminal_detail', pk=pk)
    else:
        form = POSTerminalForm(instance=terminal)

    return render(request, 'pos/terminal_form.html', {
        'form': form,
        'terminal': terminal,
        'warehouses': warehouses,
    })


@login_required
@never_cache
def terminal_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        terminal = get_object_or_404(POSTerminal, pk=pk, company=company)
    else:
        terminal = get_object_or_404(POSTerminal, pk=pk)

    if request.method == 'POST':
        name = terminal.name
        terminal.delete()
        Activity.log_activity(
            'product_deleted',
            f"POS terminal {name} deleted",
            user=request.user, company=company,
        )
        messages.success(request, get_translation('pos_terminal_deleted', lang))
        return redirect('pos:terminal_list')

    return render(request, 'pos/terminal_confirm_delete.html', {'terminal': terminal})


# ============================================================
# POS MANAGEMENT — Shift Views
# ============================================================

@login_required
@never_cache
def shift_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        shifts = CashShift.objects.filter(company=company).select_related('terminal', 'cashier')
    else:
        shifts = CashShift.objects.select_related('terminal', 'cashier').all()

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    terminal_filter = request.GET.get('terminal', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    cashier_filter = request.GET.get('cashier', '')
    if not _is_owner(request.user):
        shifts = shifts.filter(cashier=request.user)

    if q:
        shifts = shifts.filter(
            Q(shift_number__icontains=q) |
            Q(cashier__email__icontains=q) |
            Q(cashier__first_name__icontains=q) |
            Q(cashier__last_name__icontains=q)
        )
    if status_filter:
        shifts = shifts.filter(status=status_filter)
    if terminal_filter:
        shifts = shifts.filter(terminal_id=terminal_filter)
    if date_from:
        shifts = shifts.filter(opened_at__date__gte=date_from)
    if date_to:
        shifts = shifts.filter(opened_at__date__lte=date_to)

    shifts = shifts.order_by('-opened_at')
    paginator = Paginator(shifts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    terminals = POSTerminal.objects.filter(company=company, is_active=True) if company else POSTerminal.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'terminals': terminals,
        'q': q,
        'status_filter': status_filter,
        'terminal_filter': terminal_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': CashShift.SHIFT_STATUS_CHOICES,
        'total_count': paginator.count,
    }
    return render(request, 'pos/shift_list.html', context)


@login_required
@never_cache
def shift_detail(request, pk):
    company = _get_company(request)
    if company:
        shift = get_object_or_404(CashShift.objects.select_related('terminal', 'cashier'), pk=pk, company=company)
    else:
        shift = get_object_or_404(CashShift.objects.select_related('terminal', 'cashier'), pk=pk)

    receipts = shift.receipts.all().order_by('-created_at')

    shift_stats = receipts.aggregate(
        total_sales=Sum('total'),
        total_tax=Sum('tax_amount'),
        total_discount=Sum('discount_amount'),
        receipt_count=Count('id'),
    )

    payment_breakdown = receipts.values('payment_method').annotate(
        total=Sum('total'),
        count=Count('id')
    )

    movements = shift.movements.all().order_by('-created_at')

    context = {
        'shift': shift,
        'receipts': receipts,
        'shift_stats': shift_stats,
        'payment_breakdown': payment_breakdown,
        'movements': movements,
    }
    return render(request, 'pos/shift_detail.html', context)


# ============================================================
# POS MANAGEMENT — Receipt Views
# ============================================================

@login_required
@never_cache
def receipt_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        receipts = POSReceipt.objects.filter(company=company).select_related('terminal', 'shift', 'customer', 'created_by')
    else:
        receipts = POSReceipt.objects.select_related('terminal', 'shift', 'customer', 'created_by').all()

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_method', '')
    terminal_filter = request.GET.get('terminal', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    cashier_filter = request.GET.get('cashier', '')

    if q:
        receipts = receipts.filter(
            Q(receipt_number__icontains=q) |
            Q(reference__icontains=q) |
            Q(customer__name__icontains=q)
        )
    if status_filter:
        receipts = receipts.filter(status=status_filter)
    if payment_filter:
        receipts = receipts.filter(payment_method=payment_filter)
    if terminal_filter:
        receipts = receipts.filter(terminal_id=terminal_filter)
    if date_from:
        receipts = receipts.filter(created_at__date__gte=date_from)
    if date_to:
        receipts = receipts.filter(created_at__date__lte=date_to)
    if cashier_filter and _is_owner(request.user):
        receipts = receipts.filter(created_by_id=cashier_filter)

    receipts = receipts.order_by('-created_at')
    paginator = Paginator(receipts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    terminals = POSTerminal.objects.filter(company=company, is_active=True) if company else POSTerminal.objects.filter(is_active=True)

    cashiers = User.objects.filter(company=company, is_active=True).order_by('first_name', 'last_name') if company else User.objects.none()
    context = {
        'page_obj': page_obj,
        'terminals': terminals,
        'q': q,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'terminal_filter': terminal_filter,
        'date_from': date_from,
        'date_to': date_to,
        'cashier_filter': cashier_filter,
        'cashiers': cashiers,
        'is_owner': _is_owner(request.user),
        'status_choices': [('draft', 'Draft'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('refunded', 'Refunded')],
        'payment_choices': [('cash', 'Cash'), ('card', 'Card'), ('transfer', 'Transfer'), ('online', 'Online'), ('mixed', 'Mixed'), ('other', 'Other')],
        'total_count': paginator.count,
    }
    return render(request, 'pos/receipt_list.html', context)


@login_required
@never_cache
def receipt_detail(request, pk):
    company = _get_company(request)
    if company:
        receipt = get_object_or_404(
            POSReceipt.objects.select_related('terminal', 'shift', 'customer', 'created_by', 'sale'),
            pk=pk, company=company
        )
    else:
        receipt = get_object_or_404(
            POSReceipt.objects.select_related('terminal', 'shift', 'customer', 'created_by', 'sale'),
            pk=pk
        )
    if not _is_owner(request.user) and receipt.created_by_id != request.user.pk:
        return JsonResponse({'success': False, 'error': 'Bu chekni ko\'rish huquqi yo\'q'}, status=403)
    items = receipt.items.select_related('product', 'variant').all()

    context = {
        'receipt': receipt,
        'items': items,
        'returns': receipt.returns.prefetch_related('items').all(),
        'is_owner': _is_owner(request.user),
    }
    return render(request, 'pos/receipt_detail.html', context)


@login_required
@never_cache
def receipt_cancel(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        receipt = get_object_or_404(POSReceipt, pk=pk, company=company)
    else:
        receipt = get_object_or_404(POSReceipt, pk=pk)

    if not _is_owner(request.user):
        return JsonResponse({'success': False, 'error': 'Chekni bekor qilish faqat egasi uchun mavjud'}, status=403)

    if receipt.status != 'completed':
        messages.error(request, get_translation('pos_receipt_cannot_cancel', lang))
        return redirect('pos:receipt_detail', pk=pk)

    if request.method == 'POST':
        with transaction.atomic():
            receipt = POSReceipt.objects.select_for_update().get(pk=receipt.pk)
            if receipt.status != 'completed':
                return JsonResponse({'success': False, 'error': 'Chek allaqachon bekor qilingan'}, status=400)
            receipt.cancel()
            for item in receipt.items.select_related('product'):
                StockEngine.process_stock_change(product=item.product, warehouse=receipt.warehouse, company=company, direction='IN', movement_type='return_in', quantity=item.quantity, user=request.user, reference_type='POSReceipt', reference_id=receipt.pk, reference_number=receipt.receipt_number, reason=f"POS Receipt {receipt.receipt_number} cancelled: {item.product.name} x{item.quantity}")
            Activity.log_activity('product_deleted', f"POS receipt {receipt.receipt_number} cancelled", user=request.user, company=company, related_object_type='POSReceipt', related_object_id=receipt.pk)
        messages.success(request, get_translation('pos_receipt_cancelled', lang))
        return redirect('pos:receipt_detail', pk=pk)

    return render(request, 'pos/receipt_confirm_cancel.html', {'receipt': receipt})


@login_required
def api_return_sale(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    if not _is_owner(request.user):
        return JsonResponse({'success': False, 'error': 'Qaytarish faqat egasi uchun mavjud'}, status=403)
    company = _get_company(request)
    try:
        data = json.loads(request.body)
        receipt_id = data.get('receipt_id')
        requested = data.get('items', [])
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ma\'lumotlar noto\'g\'ri'}, status=400)
    if not requested:
        return JsonResponse({'success': False, 'error': 'Qaytariladigan mahsulotni tanlang'}, status=400)
    with transaction.atomic():
        receipt = POSReceipt.objects.select_for_update().filter(pk=receipt_id, company=company, status__in=['completed', 'refunded']).select_related('sale', 'terminal', 'shift', 'warehouse').first()
        if not receipt:
            return JsonResponse({'success': False, 'error': 'Chek topilmadi'}, status=404)
        sold = {item.pk: item for item in receipt.items.select_for_update().select_related('product')}
        returned = {}
        for old_return in receipt.returns.filter(status='completed').prefetch_related('items'):
            for old_item in old_return.items.all(): returned[old_item.product_id] = returned.get(old_item.product_id, Decimal('0')) + old_item.quantity
        prepared, refund_total = [], Decimal('0')
        for row in requested:
            item = sold.get(int(row.get('receipt_item_id')))
            qty = Decimal(str(row.get('quantity', '0')))
            if not item or qty <= 0 or qty > item.quantity - returned.get(item.product_id, Decimal('0')):
                return JsonResponse({'success': False, 'error': 'Qaytarish miqdori noto\'g\'ri'}, status=400)
            line_refund = (item.unit_price * qty).quantize(Decimal('0.01'))
            prepared.append((item, qty, line_refund))
            refund_total += line_refund
        is_credit = bool(receipt.sale and receipt.sale.payment_terms == 'credit' and receipt.sale.customer_id)
        refund_method = 'account_credit' if is_credit else data.get('refund_method', receipt.payment_method if receipt.payment_method in ('cash', 'card') else 'cash')
        if refund_method not in {'cash', 'card', 'account_credit'}:
            refund_method = 'cash'
        pos_return = POSReturn.objects.create(company=company, original_receipt=receipt, return_number=_next_return_number(company), terminal=receipt.terminal, shift=receipt.shift, refund_method=refund_method, refund_amount=refund_total, reason=str(data.get('reason', '')), created_by=request.user, status='completed', completed_at=timezone.now())
        for item, qty, line_refund in prepared:
            POSReturnItem.objects.create(pos_return=pos_return, product=item.product, variant=item.variant, quantity=qty, unit_price=item.unit_price, refund_amount=line_refund)
            if data.get('condition', 'sellable') == 'sellable':
                StockEngine.process_stock_change(product=item.product, warehouse=receipt.warehouse, company=company, direction='IN', movement_type='return_in', quantity=qty, user=request.user, reference_type='POSReturn', reference_id=pos_return.pk, reference_number=pos_return.return_number, reason=f'Return {pos_return.return_number}: {item.product.name}')
        if is_credit:
            debt = Debt.objects.select_for_update().filter(sale=receipt.sale, company=company).first()
            if debt:
                debt.total = max(Decimal('0'), debt.total - refund_total)
                debt.refresh_status(save=False)
                debt.save(update_fields=['total', 'status', 'updated_at'])
        else:
            FinancialTransaction.objects.create(company=company, date=timezone.localdate(), txn_type='customer_refund', direction='expense', amount=refund_total, customer=receipt.customer, reference_type='POSReturn', reference_id=pos_return.pk, reference_number=pos_return.return_number, payment_method=refund_method, description=f'Refund {pos_return.return_number}', status='completed', created_by=request.user)
            if refund_method == 'cash':
                CashMovement.objects.create(company=company, shift=receipt.shift, movement_type='refund', amount=refund_total, reference_type='POSReturn', reference_id=pos_return.pk, reference_number=pos_return.return_number, description=f'Refund {pos_return.return_number}', created_by=request.user)
        if sum((item.quantity - returned.get(item.product_id, Decimal('0')) for item in sold.values()), Decimal('0')) == sum((qty for item, qty, _ in prepared), Decimal('0')):
            receipt.status = 'refunded'
            receipt.save(update_fields=['status'])
        Activity.log_activity('product_updated', f'Return {pos_return.return_number} for receipt {receipt.receipt_number}: {refund_total}', user=request.user, company=company, related_object_type='POSReturn', related_object_id=pos_return.pk)
    return JsonResponse({'success': True, 'return_id': pos_return.pk, 'return_number': pos_return.return_number, 'refund_amount': str(refund_total), 'refund_method': refund_method})
