from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, ExpressionWrapper, DecimalField
from django.db import connection
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from datetime import timedelta
from products.models import Product
from users.models import Company
from warehouses.models import Warehouse
from finance.models import CustomerDebt, SupplierDebt, Payment
from .models import (
    Transaction, StockLevel, StockMovement, StockAdjustment,
    StockAdjustmentItem, InventoryCount, InventoryCountItem, StockEngine,
)
from .forms import (
    TransactionForm, StockAdjustmentForm, StockAdjustmentItemForm,
    InventoryCountForm, InventoryCountItemForm,
)
from core.translations import get_translation


# ============================================================
# HELPER
# ============================================================

def _company(request):
    company = getattr(request.user, 'company', None)
    if not company and request.user.is_superuser:
        default_company = Company.objects.order_by('id').first()
        if default_company:
            request.user.company = default_company
            request.user.save(update_fields=['company'])
            company = default_company
    return company


def _lang(request):
    return request.session.get('language', 'uz')


def _require_company(request):
    company = _company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return None
    return company


def _check_company_or_redirect(request):
    company = _company(request)
    if company:
        return company, None
    if request.user.is_superuser:
        return None, None
    lang = _lang(request)
    messages.error(request, get_translation('no_company_assigned', lang))
    return None, redirect('login')


def _company_qs(queryset, company):
    if company:
        return queryset.filter(company=company)
    return queryset


# ============================================================
# DASHBOARD (root /)
# ============================================================

@login_required
@never_cache
def dashboard(request):
    company = _company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    products = Product.objects.filter(company=company) if company else Product.objects.all()
    transactions = Transaction.objects.filter(company=company) if company else Transaction.objects.all()

    total_products = products.count()
    low_stock_products = products.filter(quantity__gt=0, quantity__lte=F('min_stock'))
    low_stock_count = low_stock_products.count()
    # Out-of-stock is a distinct bucket from low_stock (which requires
    # quantity > 0), so the dashboard needs its own count/rows to report
    # stock health completely. Both reuse the canonical manager methods so
    # the numbers can never drift from the low/out-of-stock list pages.
    out_of_stock_products = Product.out_of_stock_qs(company)[:5]
    out_of_stock_count = Product.out_of_stock_qs(company).count()
    overstock_count = Product.overstock_qs(company).count()
    category_counts = dict(products.values('category').annotate(count=Count('id')).values_list('category', 'count'))
    recent_transactions = transactions.select_related('product', 'user').order_by('-created_at')[:10]

    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_stock_in = transactions.filter(transaction_type='IN', created_at__gte=seven_days_ago).aggregate(total=Sum('quantity'))['total'] or 0
    recent_stock_out = transactions.filter(transaction_type='OUT', created_at__gte=seven_days_ago).aggregate(total=Sum('quantity'))['total'] or 0

    total_stock = products.aggregate(total=Sum('quantity'))['total'] or 0
    inventory_value = products.aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0
    customer_debt_total = CustomerDebt.objects.filter(company=company).aggregate(total=Sum('debt_amount'))['total'] if company else 0
    supplier_debt_total = SupplierDebt.objects.filter(company=company).aggregate(total=Sum('amount_owed'))['total'] if company else 0
    customer_debt_total = customer_debt_total or 0
    supplier_debt_total = supplier_debt_total or 0

    category_label_map = {k: get_translation(k, lang) for k in ['electronics', 'clothing', 'food', 'furniture', 'tools', 'other']}
    category_counts_translated = {category_label_map.get(k, k): v for k, v in category_counts.items()}
    # Largest slice first: the analytics chart and its legend read top-down,
    # and an unordered dict would render slices in database grouping order.
    category_counts_translated = dict(sorted(category_counts_translated.items(), key=lambda kv: kv[1], reverse=True))

    context = {
        'total_products': total_products,
        'total_stock': total_stock,
        'inventory_value': inventory_value,
        'low_stock_count': low_stock_count,
        'low_stock_products': low_stock_products[:5],
        'out_of_stock_count': out_of_stock_count,
        'out_of_stock_products': out_of_stock_products,
        'overstock_count': overstock_count,
        'recent_transactions': recent_transactions,
        'recent_stock_in': recent_stock_in,
        'recent_stock_out': recent_stock_out,
        'category_counts': category_counts_translated,
        'customer_debt_total': customer_debt_total,
        'supplier_debt_total': supplier_debt_total,
        'company': company,
    }
    return render(request, 'inventory/dashboard.html', context)


# ============================================================
# INVENTORY OVERVIEW
# ============================================================

@login_required
@never_cache
def inventory_overview(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    overview = StockEngine.get_inventory_overview(company)
    products = Product.objects.filter(company=company).select_related('category_fk', 'brand', 'unit') if company else Product.objects.all().select_related('category_fk', 'brand', 'unit')
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    recent_movements = StockMovement.objects.filter(company=company).select_related(
        'product', 'warehouse', 'user'
    ).order_by('-created_at')[:10] if company else StockMovement.objects.select_related(
        'product', 'warehouse', 'user'
    ).order_by('-created_at')[:10]

    # Same canonical buckets the tab counts come from, so each panel's
    # contents agree with the number shown on its tab. Capped at 10 for
    # the panel; the tab count is the full total.
    low_stock_products = Product.low_stock_qs(company).select_related('category_fk', 'brand', 'unit')[:10]
    out_of_stock_products = Product.out_of_stock_qs(company).select_related('category_fk', 'brand', 'unit')[:10]
    overstock_products = Product.overstock_qs(company).select_related('category_fk', 'brand', 'unit')[:10]

    context = {
        **overview,
        'warehouses': warehouses,
        'recent_movements': recent_movements,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'overstock_products': overstock_products,
    }
    return render(request, 'inventory/inventory_overview.html', context)


# ============================================================
# INVENTORY TABLE
# ============================================================

@login_required
@never_cache
def inventory_table(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    products = Product.objects.filter(company=company).select_related('category_fk', 'brand', 'unit') if company else Product.objects.all().select_related('category_fk', 'brand', 'unit')
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    brand_filter = request.GET.get('brand', '')
    warehouse_filter = request.GET.get('warehouse', '')
    sort = request.GET.get('sort', '-quantity')

    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
        )
    if status_filter in Product.STOCK_BUCKET_FILTERS:
        # Reuse the canonical bucket predicates so this table's status
        # filter agrees with stock_status and the dashboard tab counts.
        products = products.filter(**Product.STOCK_BUCKET_FILTERS[status_filter])
    if category_filter:
        products = products.filter(category_fk__id=category_filter)
    if brand_filter:
        products = products.filter(brand__id=brand_filter)

    valid_sorts = {
        'name': 'name', '-name': '-name',
        'quantity': 'quantity', '-quantity': '-quantity',
        'price': 'price', '-price': '-price',
        'purchase_price': 'purchase_price', '-purchase_price': '-purchase_price',
        'sku': 'sku', '-sku': '-sku',
        'created_at': 'created_at', '-created_at': '-created_at',
    }
    if sort in valid_sorts:
        products = products.order_by(valid_sorts[sort])

    paginator = Paginator(products, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Product.objects.filter(company=company).values_list('category_fk__id', 'category_fk__name').distinct() if company else Product.objects.values_list('category_fk__id', 'category_fk__name').distinct()
    brands = Product.objects.filter(company=company).values_list('brand__id', 'brand__name').distinct() if company else Product.objects.values_list('brand__id', 'brand__name').distinct()

    context = {
        'page_obj': page_obj,
        'warehouses': warehouses,
        'categories': [(c[0], c[1]) for c in categories if c[0]],
        'brands': [(b[0], b[1]) for b in brands if b[0]],
        'q': q,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'brand_filter': brand_filter,
        'warehouse_filter': warehouse_filter,
        'sort': sort,
        'total_count': paginator.count,
    }
    return render(request, 'inventory/inventory_table.html', context)


# ============================================================
# LOW STOCK
# ============================================================

@login_required
@never_cache
def low_stock_list(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    products = Product.low_stock_qs(company).select_related('category_fk', 'brand', 'unit')

    paginator = Paginator(products, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/low_stock_list.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
    })


# ============================================================
# OUT OF STOCK
# ============================================================

@login_required
@never_cache
def out_of_stock_list(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    products = Product.out_of_stock_qs(company).select_related('category_fk', 'brand', 'unit')

    paginator = Paginator(products, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/out_of_stock_list.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
    })


# ============================================================
# OVERSTOCK
# ============================================================

@login_required
@never_cache
def overstock_list(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    products = Product.overstock_qs(company).select_related('category_fk', 'brand', 'unit')

    paginator = Paginator(products, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/overstock_list.html', {
        'page_obj': page_obj,
        'total_count': paginator.count,
    })


# ============================================================
# STOCK MOVEMENT HISTORY
# ============================================================

# Maps a StockMovement.movement_type value to its translation key. The
# model is the single source of truth for the list itself; this map only
# supplies display text, and any value without an entry falls back to the
# model's own English label instead of leaking a raw key to the user.
_MOVEMENT_TYPE_LABEL_KEYS = {
    'opening': 'mt_opening',
    'purchase': 'mt_purchase',
    'sale': 'mt_sale',
    'transfer_in': 'transfer_in',
    'transfer_out': 'transfer_out',
    'return_in': 'mt_return_in',
    'return_out': 'mt_return_out',
    'adjustment_increase': 'adjustment_increase',
    'adjustment_decrease': 'adjustment_decrease',
    'damage': 'mt_damage',
    'loss': 'mt_loss',
    'found': 'mt_found',
    'correction': 'mt_correction',
    'stock_in': 'stock_in',
    'stock_out': 'stock_out',
}


def _movement_type_choices(lang):
    """[(value, label)] for the movement-type filter, in model order."""
    return [
        (value, get_translation(_MOVEMENT_TYPE_LABEL_KEYS.get(value, ''), lang) or label)
        for value, label in StockMovement.MOVEMENT_TYPES
    ]


@login_required
@never_cache
def movement_history(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    movements = StockMovement.objects.filter(company=company).select_related('product', 'warehouse', 'user') if company else StockMovement.objects.select_related('product', 'warehouse', 'user')

    q = request.GET.get('q', '').strip()
    movement_type = request.GET.get('movement_type', '')
    direction = request.GET.get('direction', '')
    product_id = request.GET.get('product_id', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if q:
        movements = movements.filter(
            Q(product__name__icontains=q) |
            Q(product__sku__icontains=q) |
            Q(reference_number__icontains=q)
        )
    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if direction:
        movements = movements.filter(direction=direction)
    if product_id:
        # Guard against hand-edited /malformed query strings: a non-numeric
        # value would otherwise raise ValueError on the pk lookup.
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            product_id = None
    if product_id:
        movements = movements.filter(product__id=product_id)
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)

    movements = movements.order_by('-created_at')

    paginator = Paginator(movements, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')

    context = {
        'page_obj': page_obj,
        'products': products,
        'movement_type_choices': _movement_type_choices(_lang(request)),
        'q': q,
        'movement_type': movement_type,
        'direction': direction,
        'product_id': product_id,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': paginator.count,
    }
    return render(request, 'inventory/movement_history.html', context)


# ============================================================
# STOCK ADJUSTMENTS
# ============================================================

@login_required
@never_cache
def adjustment_list(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    adjustments = StockAdjustment.objects.filter(company=company).select_related('warehouse', 'created_by', 'approved_by') if company else StockAdjustment.objects.select_related('warehouse', 'created_by', 'approved_by')

    paginator = Paginator(adjustments, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/adjustment_list.html', {
        'page_obj': page_obj,
    })


@login_required
@never_cache
def adjustment_create(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        form.fields['warehouse'].queryset = Warehouse.objects.filter(
            company=company, is_active=True
        ) if company else Warehouse.objects.filter(is_active=True)
        if form.is_valid():
            warehouse = form.cleaned_data.get('warehouse')
            adj_company = (
                getattr(warehouse, 'company', None)
                or getattr(request.user, 'company', None)
                or Company.objects.order_by('id').first()
            )
            if not adj_company:
                messages.error(request, get_translation('no_company_assigned', _lang(request)))
                return render(request, 'inventory/adjustment_form.html', {'form': form})
            adj = form.save(commit=False)
            adj.company = adj_company
            adj.created_by = request.user
            adj.save()
            messages.success(request, get_translation('adjustment_created', _lang(request)))
            return redirect('adjustment_detail', pk=adj.pk)
    else:
        form = StockAdjustmentForm()
        form.fields['warehouse'].queryset = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    return render(request, 'inventory/adjustment_form.html', {'form': form})


@login_required
@never_cache
def adjustment_detail(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    adjustment = get_object_or_404(StockAdjustment, pk=pk, company=company)
    items = adjustment.items.select_related('product')

    return render(request, 'inventory/adjustment_detail.html', {
        'adjustment': adjustment,
        'items': items,
    })


@login_required
@never_cache
def adjustment_add_item(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    adjustment = get_object_or_404(StockAdjustment, pk=pk, company=company)

    if adjustment.status not in ('draft', 'pending'):
        messages.error(request, get_translation('adjustment_locked', _lang(request)))
        return redirect('adjustment_detail', pk=pk)

    if request.method == 'POST':
        product_id = request.POST.get('product')
        actual_qty = request.POST.get('actual_quantity', 0)
        notes = request.POST.get('notes', '')

        product = get_object_or_404(Product, pk=product_id, company=company)
        expected = product.quantity

        item = StockAdjustmentItem.objects.create(
            adjustment=adjustment,
            product=product,
            expected_quantity=expected,
            actual_quantity=int(actual_qty),
            notes=notes,
        )
        item.save()
        messages.success(request, get_translation('item_added', _lang(request)))
        return redirect('adjustment_detail', pk=pk)

    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')
    return render(request, 'inventory/adjustment_add_item.html', {
        'adjustment': adjustment,
        'products': products,
    })


@login_required
@never_cache
def adjustment_submit(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    adjustment = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if adjustment.status == 'draft':
        adjustment.status = 'pending'
        adjustment.save(update_fields=['status', 'updated_at'])
        messages.success(request, get_translation('adjustment_submitted', _lang(request)))

    return redirect('adjustment_detail', pk=pk)


@login_required
@never_cache
def adjustment_approve(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    adjustment = get_object_or_404(StockAdjustment, pk=pk, company=company)
    if adjustment.status == 'pending':
        adjustment.status = 'approved'
        adjustment.approved_by = request.user
        adjustment.save(update_fields=['status', 'approved_by', 'updated_at'])

        for item in adjustment.items.all():
            if item.difference != 0:
                direction = 'IN' if item.difference > 0 else 'OUT'
                StockEngine.process_stock_change(
                    product=item.product,
                    warehouse=adjustment.warehouse,
                    company=company,
                    direction=direction,
                    movement_type='adjustment_increase' if item.difference > 0 else 'adjustment_decrease',
                    quantity=abs(item.difference),
                    user=request.user,
                    reference_type='StockAdjustment',
                    reference_id=adjustment.pk,
                    reference_number=adjustment.reference,
                    reason=adjustment.reason or 'Stock Adjustment',
                )

        adjustment.status = 'completed'
        adjustment.save(update_fields=['status', 'updated_at'])
        messages.success(request, get_translation('adjustment_approved', _lang(request)))

    return redirect('adjustment_detail', pk=pk)


# ============================================================
# INVENTORY COUNT / STOCKTAKE
# ============================================================

@login_required
@never_cache
def count_list(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    counts = InventoryCount.objects.filter(company=company).select_related('warehouse', 'created_by') if company else InventoryCount.objects.select_related('warehouse', 'created_by')

    paginator = Paginator(counts, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/count_list.html', {'page_obj': page_obj})


@login_required
@never_cache
def count_create(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = InventoryCountForm(request.POST)
        if form.is_valid():
            count = form.save(commit=False)
            count.company = company
            count.created_by = request.user
            count.status = 'draft'
            count.save()

            warehouse = count.warehouse
            products = Product.objects.filter(company=company, quantity__gte=0).order_by('name') if company else Product.objects.filter(quantity__gte=0).order_by('name')
            for product in products:
                InventoryCountItem.objects.create(
                    count=count,
                    product=product,
                    expected_quantity=product.quantity,
                )

            messages.success(request, get_translation('count_created', _lang(request)))
            return redirect('count_detail', pk=count.pk)
    else:
        form = InventoryCountForm()
        form.fields['warehouse'].queryset = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    return render(request, 'inventory/count_form.html', {'form': form})


@login_required
@never_cache
def count_detail(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    count = get_object_or_404(InventoryCount, pk=pk, company=company)
    items = count.items.select_related('product').order_by('product__name')

    q = request.GET.get('q', '').strip()
    if q:
        items = items.filter(Q(product__name__icontains=q) | Q(product__sku__icontains=q))

    paginator = Paginator(items, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'count': count,
        'page_obj': page_obj,
        'q': q,
    }
    return render(request, 'inventory/count_detail.html', context)


@login_required
@never_cache
def count_start(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    count = get_object_or_404(InventoryCount, pk=pk, company=company)
    if count.status == 'draft':
        count.status = 'in_progress'
        count.started_at = timezone.now()
        count.save(update_fields=['status', 'started_at', 'updated_at'])
        messages.success(request, get_translation('count_started', _lang(request)))

    return redirect('count_detail', pk=pk)


@login_required
@never_cache
def count_item_update(request, count_pk, item_pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    count = get_object_or_404(InventoryCount, pk=count_pk, company=company)
    item = get_object_or_404(InventoryCountItem, pk=item_pk, count=count)

    if request.method == 'POST':
        actual = request.POST.get('actual_quantity', '')
        notes = request.POST.get('notes', '')
        if actual != '':
            item.actual_quantity = int(actual)
            item.notes = notes
            item.save(update_fields=['actual_quantity', 'difference', 'notes'])

    redirect_url = request.GET.get('next', f'/inventory/counts/{count.pk}/')
    return redirect(redirect_url)


@login_required
@never_cache
def count_submit(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    count = get_object_or_404(InventoryCount, pk=pk, company=company)
    if count.status == 'in_progress':
        count.status = 'submitted'
        count.completed_at = timezone.now()
        count.save(update_fields=['status', 'completed_at', 'updated_at'])
        messages.success(request, get_translation('count_submitted', _lang(request)))

    return redirect('count_detail', pk=pk)


@login_required
@never_cache
def count_approve(request, pk):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    count = get_object_or_404(InventoryCount, pk=pk, company=company)
    if count.status == 'submitted':
        for item in count.items.filter(actual_quantity__isnull=False):
            if item.difference != 0:
                direction = 'IN' if item.difference > 0 else 'OUT'
                StockEngine.process_stock_change(
                    product=item.product,
                    warehouse=count.warehouse,
                    company=company,
                    direction=direction,
                    movement_type='adjustment_increase' if item.difference > 0 else 'adjustment_decrease',
                    quantity=abs(item.difference),
                    user=request.user,
                    reference_type='InventoryCount',
                    reference_id=count.pk,
                    reference_number=count.reference,
                    reason=f'Stocktake: {count.reference}',
                )

        count.status = 'completed'
        count.approved_by = request.user
        count.completed_at = timezone.now()
        count.save(update_fields=['status', 'approved_by', 'completed_at', 'updated_at'])
        messages.success(request, get_translation('count_approved', _lang(request)))

    return redirect('count_detail', pk=pk)


# ============================================================
# TRANSACTION VIEWS (preserved)
# ============================================================

@login_required
@never_cache
def transaction_list(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    transactions = Transaction.objects.select_related('product', 'user').order_by('-created_at')
    if company:
        transactions = transactions.filter(company=company)

    paginator = Paginator(transactions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventory/transaction_list.html', {'page_obj': page_obj})


@login_required
@never_cache
def stock_in(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.transaction_type = 'IN'
            transaction.user = request.user
            transaction.company = company
            transaction.save()

            product = transaction.product
            warehouse = Warehouse.objects.filter(company=company, is_active=True).first() if company else Warehouse.objects.filter(is_active=True).first()
            if warehouse:
                StockEngine.process_stock_change(
                    product=product, warehouse=warehouse, company=company,
                    direction='IN', movement_type='stock_in',
                    quantity=transaction.quantity, user=request.user,
                    reference_type='Transaction', reference_id=transaction.pk,
                    notes=transaction.notes,
                )

            messages.success(request, get_translation('stock_in_success', _lang(request)))
            return redirect('dashboard')
    else:
        form = TransactionForm()
        form.fields['product'].queryset = Product.objects.filter(company=company) if company else Product.objects.all()

    return render(request, 'inventory/transaction_form.html', {
        'form': form,
        'title': get_translation('stock_in', _lang(request)),
        'transaction_type': 'IN',
    })


@login_required
@never_cache
def stock_out(request):
    company, redirect_response = _check_company_or_redirect(request)
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            quantity = form.cleaned_data['quantity']

            if product.quantity < quantity:
                messages.error(request, f"{get_translation('insufficient_stock', _lang(request))}: {product.quantity}")
                return render(request, 'inventory/transaction_form.html', {
                    'form': form,
                    'title': get_translation('stock_out', _lang(request)),
                    'transaction_type': 'OUT',
                })

            transaction = form.save(commit=False)
            transaction.transaction_type = 'OUT'
            transaction.user = request.user
            transaction.company = company
            transaction.save()

            warehouse = Warehouse.objects.filter(company=company, is_active=True).first() if company else Warehouse.objects.filter(is_active=True).first()
            if warehouse:
                StockEngine.process_stock_change(
                    product=product, warehouse=warehouse, company=company,
                    direction='OUT', movement_type='stock_out',
                    quantity=transaction.quantity, user=request.user,
                    reference_type='Transaction', reference_id=transaction.pk,
                    notes=transaction.notes,
                )

            messages.success(request, get_translation('stock_out_success', _lang(request)))
            return redirect('dashboard')
    else:
        form = TransactionForm()
        form.fields['product'].queryset = Product.objects.filter(company=company) if company else Product.objects.all()

    return render(request, 'inventory/transaction_form.html', {
        'form': form,
        'title': get_translation('stock_out', _lang(request)),
        'transaction_type': 'OUT',
    })


@login_required
@never_cache
def business_insights(request):
    company = _company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    products = Product.objects.filter(company=company) if company else Product.objects.all()
    payments = Payment.objects.filter(company=company) if company else Payment.objects.all()
    customer_debts = CustomerDebt.objects.filter(company=company) if company else CustomerDebt.objects.all()
    supplier_debts = SupplierDebt.objects.filter(company=company) if company else SupplierDebt.objects.all()

    total_product_value = products.aggregate(total=Sum(F('quantity') * F('price')))['total'] or 0
    thirty_days_ago = timezone.now() - timedelta(days=30)
    monthly_collections = payments.filter(payment_date__gte=thirty_days_ago).aggregate(total=Sum('amount'))['total'] or 0
    overdue_customer = customer_debts.filter(due_date__lt=timezone.now().date(), payment_status__in=['unpaid', 'partial']).count()
    overdue_supplier = supplier_debts.filter(due_date__lt=timezone.now().date(), payment_status__in=['unpaid', 'partial']).count()
    overdue_count = overdue_customer + overdue_supplier
    thirty_days_from_now = timezone.now().date() + timedelta(days=30)
    expiring_count = products.filter(expiration_date__lte=thirty_days_from_now, expiration_date__gte=timezone.now().date()).count()

    category_data = {}
    for category, label in Product.CATEGORY_CHOICES:
        count = products.filter(category=category).count()
        if count > 0:
            category_data[label] = count

    stock_status_data = {
        'labels': [get_translation(k, lang) for k in ['out_of_stock', 'low_stock', 'medium_stock', 'in_stock']],
        'data': [
            products.filter(quantity=0).count(),
            products.filter(quantity__gt=0, quantity__lt=5).count(),
            products.filter(quantity__gte=5, quantity__lt=10).count(),
            products.filter(quantity__gte=10).count(),
        ],
    }

    expiration_data = {
        'labels': [get_translation(k, lang) for k in ['not_set', 'good', 'expiring_soon', 'expired']],
        'data': [
            products.filter(expiration_date__isnull=True).count(),
            products.filter(expiration_date__gt=thirty_days_from_now).count(),
            products.filter(expiration_date__lte=thirty_days_from_now, expiration_date__gte=timezone.now().date()).count(),
            products.filter(expiration_date__lt=timezone.now().date()).count(),
        ],
    }

    top_products = products.annotate(
        total_value=ExpressionWrapper(F('quantity') * F('price'), output_field=DecimalField())
    ).order_by('-total_value')[:10]

    context = {
        'total_product_value': total_product_value,
        'monthly_collections': monthly_collections,
        'overdue_count': overdue_count,
        'expiring_count': expiring_count,
        'category_data': category_data,
        'stock_status_data': stock_status_data,
        'expiration_data': expiration_data,
        'top_products': top_products,
    }
    return render(request, 'inventory/business_insights.html', context)
