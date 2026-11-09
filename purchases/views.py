from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db.models import Sum, Count, Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from .models import Purchase, PurchaseItem, Supplier, PurchaseReturn, PurchaseReturnItem
from .forms import (
    SupplierForm, PurchaseForm, PurchaseItemForm,
    PurchaseReceiveForm, PurchaseReturnForm, PurchaseReturnItemForm,
)
from products.models import Product
from warehouses.models import Warehouse
from inventory.models import StockEngine, StockMovement
from finance.models import SupplierDebt, Payment
from activity.models import Activity
from core.translations import get_translation


def _lang(request):
    return request.session.get('language', 'uz')


def _company(request):
    return getattr(request.user, 'company', None)


def _get_company(request):
    company = _company(request)
    if not company and not request.user.is_superuser:
        return None
    return company


def _next_ref(company, prefix='PO'):
    if company:
        count = Purchase.objects.filter(company=company).count()
    else:
        count = Purchase.objects.count()
    return f"{prefix}-{count + 1:04d}"


def _next_return_ref(company):
    if company:
        count = PurchaseReturn.objects.filter(company=company).count()
    else:
        count = PurchaseReturn.objects.count()
    return f"PR-{count + 1:04d}"


# ============================================================
# PURCHASE DASHBOARD
# ============================================================

@login_required
@never_cache
def purchase_dashboard(request):
    company = _get_company(request)
    lang = _lang(request)

    if company:
        purchases = Purchase.objects.filter(company=company)
        suppliers = Supplier.objects.filter(company=company)
    else:
        purchases = Purchase.objects.all()
        suppliers = Supplier.objects.all()

    today = timezone.now().date()
    month_start = today.replace(day=1)

    context = {
        'purchases_today': purchases.filter(order_date=today).count(),
        'purchases_month': purchases.filter(order_date__gte=month_start).count(),
        'pending_purchases': purchases.filter(status__in=['draft', 'pending_approval']).count(),
        'awaiting_delivery': purchases.filter(status='ordered').count(),
        'partially_received': purchases.filter(status='partially_received').count(),
        'overdue_count': purchases.filter(
            expected_delivery_date__lt=today,
            status__in=['ordered', 'partially_received']
        ).count(),
        'total_value': purchases.aggregate(t=Sum('total'))['t'] or 0,
        'unpaid_value': purchases.exclude(payment_status='paid').aggregate(t=Sum('total'))['t'] or 0,
        'top_suppliers': suppliers.annotate(
            purchase_count=Count('purchases'),
            total_value=Sum('purchases__total')
        ).order_by('-total_value')[:5],
        'recent_purchases': purchases.select_related('supplier', 'warehouse').order_by('-created_at')[:10],
        'overdue_purchases': purchases.filter(
            expected_delivery_date__lt=today,
            status__in=['ordered', 'partially_received']
        ).select_related('supplier')[:5],
    }
    return render(request, 'purchases/purchase_dashboard.html', context)


# ============================================================
# PURCHASES CRUD
# ============================================================

@login_required
@never_cache
def purchase_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        purchases = Purchase.objects.filter(company=company).select_related('supplier', 'warehouse', 'created_by')
    else:
        purchases = Purchase.objects.select_related('supplier', 'warehouse', 'created_by').all()

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment', '')
    supplier_filter = request.GET.get('supplier', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if q:
        purchases = purchases.filter(
            Q(reference__icontains=q) |
            Q(supplier__name__icontains=q) |
            Q(items__product__name__icontains=q) |
            Q(items__product__sku__icontains=q)
        ).distinct()
    if status_filter:
        purchases = purchases.filter(status=status_filter)
    if payment_filter:
        purchases = purchases.filter(payment_status=payment_filter)
    if supplier_filter:
        purchases = purchases.filter(supplier_id=supplier_filter)
    if date_from:
        purchases = purchases.filter(order_date__gte=date_from)
    if date_to:
        purchases = purchases.filter(order_date__lte=date_to)

    purchases = purchases.order_by('-created_at')
    paginator = Paginator(purchases, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    suppliers = Supplier.objects.filter(company=company, is_active=True) if company else Supplier.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'suppliers': suppliers,
        'q': q,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'supplier_filter': supplier_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Purchase.STATUS_CHOICES,
        'payment_choices': Purchase.PAYMENT_STATUS_CHOICES,
        'total_count': paginator.count,
    }
    return render(request, 'purchases/purchase_list.html', context)


@login_required
@never_cache
def purchase_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    suppliers = Supplier.objects.filter(company=company, is_active=True) if company else Supplier.objects.filter(is_active=True)
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)
    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        warehouse_id = request.POST.get('warehouse')
        if supplier_id and warehouse_id:
            purchase = Purchase.objects.create(
                company=company,
                reference=_next_ref(company),
                supplier_id=int(supplier_id),
                warehouse_id=int(warehouse_id),
                expected_delivery_date=request.POST.get('expected_delivery_date') or None,
                payment_terms=request.POST.get('payment_terms', 'cod'),
                currency=request.POST.get('currency', 'UZS'),
                discount=float(request.POST.get('discount', 0) or 0),
                tax=float(request.POST.get('tax', 0) or 0),
                notes=request.POST.get('notes', ''),
                created_by=request.user,
            )
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            discounts = request.POST.getlist('item_discounts')
            taxes = request.POST.getlist('item_taxes')
            for i, pid in enumerate(product_ids):
                if pid and quantities[i] and prices[i]:
                    PurchaseItem.objects.create(
                        purchase=purchase,
                        product_id=int(pid),
                        quantity=int(quantities[i]),
                        unit_price=float(prices[i]),
                        discount=float(discounts[i]) if i < len(discounts) and discounts[i] else 0,
                        tax=float(taxes[i]) if i < len(taxes) and taxes[i] else 0,
                    )
            purchase.calculate_total()
            Activity.log_activity(
                'product_added', f"Purchase {purchase.reference} created",
                user=request.user, company=company
            )
            messages.success(request, get_translation('purchase_created', lang))
            return redirect('purchases:purchase_detail', pk=purchase.pk)
        messages.error(request, get_translation('fill_required_fields', lang))

    return render(request, 'purchases/purchase_form.html', {
        'suppliers': suppliers, 'warehouses': warehouses, 'products': products,
        'payment_terms_choices': Purchase.PAYMENT_TERMS_CHOICES,
        'currency_choices': Purchase.CURRENCY_CHOICES,
    })


@login_required
@never_cache
def purchase_detail(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'warehouse', 'created_by', 'approved_by'), pk=pk, company=company)
    else:
        purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'warehouse', 'created_by', 'approved_by'), pk=pk)
    items = purchase.items.select_related('product').all()
    returns = purchase.returns.all()

    return render(request, 'purchases/purchase_detail.html', {
        'purchase': purchase, 'items': items, 'returns': returns,
    })


@login_required
@never_cache
def purchase_update(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        purchase = get_object_or_404(Purchase, pk=pk, company=company)
    else:
        purchase = get_object_or_404(Purchase, pk=pk)

    if purchase.status not in ('draft', 'pending_approval'):
        messages.error(request, get_translation('purchase_edit_status_error', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    suppliers = Supplier.objects.filter(company=company, is_active=True) if company else Supplier.objects.filter(is_active=True)
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)
    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')
    existing_items = purchase.items.all()

    if request.method == 'POST':
        purchase.supplier_id = int(request.POST.get('supplier', purchase.supplier_id))
        purchase.warehouse_id = int(request.POST.get('warehouse', purchase.warehouse_id))
        purchase.expected_delivery_date = request.POST.get('expected_delivery_date') or purchase.expected_delivery_date
        purchase.payment_terms = request.POST.get('payment_terms', purchase.payment_terms)
        purchase.currency = request.POST.get('currency', purchase.currency)
        purchase.discount = float(request.POST.get('discount', 0) or 0)
        purchase.tax = float(request.POST.get('tax', 0) or 0)
        purchase.notes = request.POST.get('notes', purchase.notes)
        purchase.save()
        purchase.items.all().delete()
        product_ids = request.POST.getlist('products')
        quantities = request.POST.getlist('quantities')
        prices = request.POST.getlist('prices')
        discounts = request.POST.getlist('item_discounts')
        taxes = request.POST.getlist('item_taxes')
        for i, pid in enumerate(product_ids):
            if pid and quantities[i] and prices[i]:
                PurchaseItem.objects.create(
                    purchase=purchase,
                    product_id=int(pid),
                    quantity=int(quantities[i]),
                    unit_price=float(prices[i]),
                    discount=float(discounts[i]) if i < len(discounts) and discounts[i] else 0,
                    tax=float(taxes[i]) if i < len(taxes) and taxes[i] else 0,
                )
        purchase.calculate_total()
        messages.success(request, get_translation('purchase_updated', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    return render(request, 'purchases/purchase_form.html', {
        'suppliers': suppliers, 'warehouses': warehouses, 'products': products,
        'purchase': purchase, 'items': existing_items,
        'payment_terms_choices': Purchase.PAYMENT_TERMS_CHOICES,
        'currency_choices': Purchase.CURRENCY_CHOICES,
    })


@login_required
@never_cache
def purchase_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        purchase = get_object_or_404(Purchase, pk=pk, company=company)
    else:
        purchase = get_object_or_404(Purchase, pk=pk)

    if request.method == 'POST':
        if purchase.status not in ('draft', 'cancelled'):
            messages.error(request, get_translation('purchase_delete_status_error', lang))
            return redirect('purchases:purchase_detail', pk=pk)
        purchase.delete()
        messages.success(request, get_translation('purchase_deleted', lang))
        return redirect('purchases:purchase_list')

    return render(request, 'purchases/purchase_confirm_delete.html', {'purchase': purchase})


# ============================================================
# PURCHASE STATUS / WORKFLOW
# ============================================================

@login_required
@never_cache
def purchase_update_status(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        purchase = get_object_or_404(Purchase, pk=pk, company=company)
    else:
        purchase = get_object_or_404(Purchase, pk=pk)

    new_status = request.POST.get('status')
    if not new_status or not purchase.can_transition(new_status):
        messages.error(request, get_translation('invalid_status_transition', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    try:
        purchase.transition_to(new_status)
        if new_status == 'approved':
            purchase.approved_by = request.user
            purchase.save(update_fields=['approved_by'])
        Activity.log_activity(
            'product_updated',
            f"Purchase {purchase.reference} status: {purchase.get_status_display()}",
            user=request.user, company=company
        )
        messages.success(request, get_translation('purchase_status_updated', lang))
    except Exception as e:
        messages.error(request, str(e))

    return redirect('purchases:purchase_detail', pk=pk)


# ============================================================
# PURCHASE RECEIVING
# ============================================================

@login_required
@never_cache
def purchase_receive(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'warehouse'), pk=pk, company=company)
    else:
        purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'warehouse'), pk=pk)

    if purchase.status not in ('ordered', 'partially_received'):
        messages.error(request, get_translation('purchase_receive_status_error', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    items = purchase.items.select_related('product').all()

    if request.method == 'POST':
        any_received = False
        for item in items:
            received = int(request.POST.get(f'received_{item.id}', 0) or 0)
            damaged = int(request.POST.get(f'damaged_{item.id}', 0) or 0)
            rejected = int(request.POST.get(f'rejected_{item.id}', 0) or 0)

            if received > 0 or damaged > 0 or rejected > 0:
                effective = received - damaged - rejected
                if effective > 0:
                    StockEngine.process_stock_change(
                        product=item.product,
                        warehouse=purchase.warehouse,
                        company=company or purchase.company,
                        direction='IN',
                        movement_type='purchase_receive',
                        quantity=effective,
                        user=request.user,
                        reference_type='Purchase',
                        reference_id=purchase.pk,
                        reference_number=purchase.reference,
                        reason=f"Received {item.product.name} x{effective} for {purchase.reference}",
                    )
                item.received_quantity += received
                item.damaged_quantity += damaged
                item.rejected_quantity += rejected
                item.save(update_fields=['received_quantity', 'damaged_quantity', 'rejected_quantity'])
                any_received = True

        all_received = all(it.is_fully_received for it in items)
        some_received = any(it.received_quantity > 0 for it in items)

        if all_received:
            purchase.status = 'received'
        elif some_received:
            purchase.status = 'partially_received'
        purchase.save(update_fields=['status', 'updated_at'])

        Activity.log_activity(
            'stock_in',
            f"Purchase {purchase.reference} receiving completed",
            user=request.user, company=company
        )
        messages.success(request, get_translation('products_received', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    return render(request, 'purchases/purchase_receive.html', {
        'purchase': purchase, 'items': items,
    })


# ============================================================
# PURCHASE RETURNS
# ============================================================

@login_required
@never_cache
def purchase_return_create(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'warehouse'), pk=pk, company=company)
    else:
        purchase = get_object_or_404(Purchase.objects.select_related('supplier', 'warehouse'), pk=pk)

    if purchase.status not in ('received', 'partially_received'):
        messages.error(request, get_translation('purchase_return_status_error', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    receivable_items = purchase.items.filter(
        received_quantity__gt=0
    ).select_related('product')

    if request.method == 'POST':
        return_order = PurchaseReturn.objects.create(
            company=company,
            purchase=purchase,
            reference=_next_return_ref(company),
            supplier=purchase.supplier,
            warehouse=purchase.warehouse,
            reason=request.POST.get('reason', 'other'),
            reason_notes=request.POST.get('reason_notes', ''),
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )
        item_ids = request.POST.getlist('return_items')
        quantities = request.POST.getlist('return_quantities')
        for item_id, qty in zip(item_ids, quantities):
            if item_id and qty and int(qty) > 0:
                purchase_item = PurchaseItem.objects.get(pk=int(item_id))
                PurchaseReturnItem.objects.create(
                    return_order=return_order,
                    purchase_item=purchase_item,
                    product=purchase_item.product,
                    quantity=int(qty),
                    unit_price=purchase_item.unit_price,
                )
                effective = int(qty)
                StockEngine.process_stock_change(
                    product=purchase_item.product,
                    warehouse=purchase.warehouse,
                    company=company or purchase.company,
                    direction='OUT',
                    movement_type='purchase_return',
                    quantity=effective,
                    user=request.user,
                    reference_type='PurchaseReturn',
                    reference_id=return_order.pk,
                    reference_number=return_order.reference,
                    reason=f"Return {purchase_item.product.name} x{effective} for {purchase.reference}",
                )
        return_order.calculate_total()
        messages.success(request, get_translation('purchase_return_created', lang))
        return redirect('purchases:purchase_detail', pk=pk)

    return render(request, 'purchases/purchase_return_form.html', {
        'purchase': purchase, 'receivable_items': receivable_items,
    })


@login_required
@never_cache
def purchase_return_detail(request, pk):
    company = _get_company(request)
    if company:
        return_order = get_object_or_404(
            PurchaseReturn.objects.select_related('purchase', 'supplier', 'warehouse'),
            pk=pk, company=company
        )
    else:
        return_order = get_object_or_404(
            PurchaseReturn.objects.select_related('purchase', 'supplier', 'warehouse'),
            pk=pk
        )
    items = return_order.items.select_related('product', 'purchase_item').all()
    return render(request, 'purchases/purchase_return_detail.html', {
        'return_order': return_order, 'items': items,
    })


@login_required
@never_cache
def purchase_return_update_status(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        return_order = get_object_or_404(PurchaseReturn, pk=pk, company=company)
    else:
        return_order = get_object_or_404(PurchaseReturn, pk=pk)

    new_status = request.POST.get('status')
    if new_status in dict(PurchaseReturn.STATUS_CHOICES):
        return_order.status = new_status
        return_order.save(update_fields=['status', 'updated_at'])
        messages.success(request, get_translation('return_status_updated', lang))

    return redirect('purchases:purchase_return_detail', pk=pk)


# ============================================================
# SUPPLIER MANAGEMENT
# ============================================================

@login_required
@never_cache
def supplier_list(request):
    company = _get_company(request)
    if not company and not request.user.is_superuser:
        return redirect('login')

    suppliers = Supplier.objects.filter(company=company) if company else Supplier.objects.all()

    q = request.GET.get('q', '').strip()
    if q:
        suppliers = suppliers.filter(
            Q(name__icontains=q) |
            Q(contact_person__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q)
        )

    suppliers = suppliers.annotate(
        purchase_count_count=Count('purchases'),
        total_value=Sum('purchases__total'),
    ).order_by('name')

    paginator = Paginator(suppliers, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'purchases/supplier_list.html', {
        'page_obj': page_obj, 'q': q,
    })


@login_required
@never_cache
def supplier_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        return redirect('login')

    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save(commit=False)
            supplier.company = company
            supplier.save()
            messages.success(request, get_translation('supplier_created', lang))
            return redirect('purchases:supplier_list')
    else:
        form = SupplierForm()

    return render(request, 'purchases/supplier_form.html', {'form': form})


@login_required
@never_cache
def supplier_detail(request, pk):
    company = _get_company(request)
    if company:
        supplier = get_object_or_404(Supplier, pk=pk, company=company)
    else:
        supplier = get_object_or_404(Supplier, pk=pk)

    purchases = Purchase.objects.filter(supplier=supplier).order_by('-created_at')[:20]
    recent_payments = Payment.objects.filter(
        supplier_debt__supplier_name=supplier.name,
        company=company,
    ).order_by('-payment_date')[:10] if company else Payment.objects.none()

    context = {
        'supplier': supplier,
        'purchases': purchases,
        'recent_payments': recent_payments,
        'total_purchases': supplier.total_purchases,
        'total_paid': supplier.total_paid,
        'total_unpaid': supplier.total_unpaid,
        'purchase_count': supplier.purchase_count,
    }
    return render(request, 'purchases/supplier_detail.html', context)


@login_required
@never_cache
def supplier_update(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        supplier = get_object_or_404(Supplier, pk=pk, company=company)
    else:
        supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('supplier_updated', lang))
            return redirect('purchases:supplier_list')
    else:
        form = SupplierForm(instance=supplier)

    return render(request, 'purchases/supplier_form.html', {'form': form, 'supplier': supplier})


@login_required
@never_cache
def supplier_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        supplier = get_object_or_404(Supplier, pk=pk, company=company)
    else:
        supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == 'POST':
        supplier.delete()
        messages.success(request, get_translation('supplier_deleted', lang))
        return redirect('purchases:supplier_list')

    return render(request, 'purchases/supplier_confirm_delete.html', {'supplier': supplier})
