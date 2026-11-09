from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db.models import Sum, Count, Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal
from .models import Customer, Sale, SaleItem, SaleReturn, SaleReturnItem, SalePayment
from .forms import CustomerForm, SaleForm, SaleItemForm, SaleReturnForm, SalePaymentForm
from products.models import Product
from warehouses.models import Warehouse
from inventory.models import StockEngine, StockMovement
from activity.models import Activity
from core.translations import get_translation


def _lang(request):
    return request.session.get('language', 'uz')


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if not company and not request.user.is_superuser:
        return None
    return company


def _next_ref(company, prefix='SO'):
    if company:
        count = Sale.objects.filter(company=company).count()
    else:
        count = Sale.objects.count()
    return f"{prefix}-{count + 1:04d}"


def _next_return_ref(company):
    if company:
        count = SaleReturn.objects.filter(company=company).count()
    else:
        count = SaleReturn.objects.count()
    return f"SR-{count + 1:04d}"


# ============================================================
# SALE DASHBOARD
# ============================================================

@login_required
@never_cache
def sale_dashboard(request):
    company = _get_company(request)
    lang = _lang(request)

    if company:
        sales = Sale.objects.filter(company=company)
        customers = Customer.objects.filter(company=company)
        returns = SaleReturn.objects.filter(company=company)
    else:
        sales = Sale.objects.all()
        customers = Customer.objects.all()
        returns = SaleReturn.objects.all()

    today = timezone.now().date()
    month_start = today.replace(day=1)

    context = {
        'sales_today': sales.filter(created_at__date=today).count(),
        'sales_month': sales.filter(created_at__date__gte=month_start).count(),
        'pending_fulfillment': sales.filter(status__in=['confirmed', 'reserved', 'picking', 'packed', 'shipped']).count(),
        'reserved_stock_value': StockEngine.get_inventory_overview(company)['total_reserved'] if company else 0,
        'unpaid_total': sales.exclude(payment_status='paid').aggregate(t=Sum('total'))['t'] or 0,
        'overdue_count': sales.filter(payment_status='overdue').count(),
        'top_customers': customers.annotate(
            sales_cnt=Count('sales'),
            total_value=Sum('sales__total'),
        ).order_by('-total_value')[:5],
        'recent_sales': sales.select_related('customer', 'warehouse').order_by('-created_at')[:10],
        'returns_pending': returns.filter(status='draft').count(),
    }
    return render(request, 'sales/sale_dashboard.html', context)


# ============================================================
# SALE LIST
# ============================================================

@login_required
@never_cache
def sale_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        sales = Sale.objects.filter(company=company).select_related('customer', 'warehouse', 'created_by')
    else:
        sales = Sale.objects.select_related('customer', 'warehouse', 'created_by').all()

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_status', '')
    customer_filter = request.GET.get('customer', '')
    warehouse_filter = request.GET.get('warehouse', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if q:
        sales = sales.filter(
            Q(reference__icontains=q) |
            Q(customer__name__icontains=q) |
            Q(items__product__name__icontains=q) |
            Q(items__product__sku__icontains=q)
        ).distinct()
    if status_filter:
        sales = sales.filter(status=status_filter)
    if payment_filter:
        sales = sales.filter(payment_status=payment_filter)
    if customer_filter:
        sales = sales.filter(customer_id=customer_filter)
    if warehouse_filter:
        sales = sales.filter(warehouse_id=warehouse_filter)
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    sales = sales.order_by('-created_at')
    paginator = Paginator(sales, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    customers = Customer.objects.filter(company=company, is_active=True) if company else Customer.objects.filter(is_active=True)
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)

    context = {
        'page_obj': page_obj,
        'customers': customers,
        'warehouses': warehouses,
        'q': q,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'customer_filter': customer_filter,
        'warehouse_filter': warehouse_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Sale.STATUS_CHOICES,
        'payment_choices': Sale.PAYMENT_STATUS_CHOICES,
        'total_count': paginator.count,
    }
    return render(request, 'sales/sale_list.html', context)


# ============================================================
# SALE CREATE
# ============================================================

@login_required
@never_cache
def sale_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    customers = Customer.objects.filter(company=company, is_active=True) if company else Customer.objects.filter(is_active=True)
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)
    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')

    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        warehouse_id = request.POST.get('warehouse')
        if customer_id and warehouse_id:
            sale = Sale.objects.create(
                company=company,
                reference=_next_ref(company),
                customer_id=int(customer_id),
                warehouse_id=int(warehouse_id),
                expected_delivery_date=request.POST.get('expected_delivery_date') or None,
                payment_terms=request.POST.get('payment_terms', 'cod'),
                currency=request.POST.get('currency', 'UZS'),
                discount=Decimal(request.POST.get('discount', '0') or '0'),
                tax=Decimal(request.POST.get('tax', '0') or '0'),
                notes=request.POST.get('notes', ''),
                created_by=request.user,
            )
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            discounts = request.POST.getlist('item_discounts')
            taxes = request.POST.getlist('item_taxes')

            with transaction.atomic():
                for i, pid in enumerate(product_ids):
                    if pid and quantities[i] and prices[i]:
                        qty = int(quantities[i])
                        product = Product.objects.get(pk=int(pid))
                        available = StockEngine.get_available(product, company) if company else product.quantity
                        if qty > available:
                            messages.warning(request, f"{product.name}: available {available}, requested {qty}")
                        SaleItem.objects.create(
                            sale=sale,
                            product_id=int(pid),
                            quantity=qty,
                            unit_price=Decimal(prices[i]),
                            discount=Decimal(discounts[i]) if i < len(discounts) and discounts[i] else Decimal('0'),
                            tax=Decimal(taxes[i]) if i < len(taxes) and taxes[i] else Decimal('0'),
                        )
            sale.calculate_total()

            Activity.log_activity(
                'product_added',
                f"Sale {sale.reference} created",
                user=request.user, company=company,
                related_object_type='Sale', related_object_id=sale.pk,
            )
            messages.success(request, get_translation('sale_created', lang))
            return redirect('sales:sale_detail', pk=sale.pk)
        messages.error(request, get_translation('please_fill_required', lang))

    return render(request, 'sales/sale_form.html', {
        'customers': customers, 'warehouses': warehouses, 'products': products,
        'payment_terms_choices': Sale.PAYMENT_TERMS_CHOICES,
        'currency_choices': Sale.CURRENCY_CHOICES,
    })


# ============================================================
# SALE DETAIL
# ============================================================

@login_required
@never_cache
def sale_detail(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(
            Sale.objects.select_related('customer', 'warehouse', 'created_by', 'approved_by'),
            pk=pk, company=company
        )
    else:
        sale = get_object_or_404(
            Sale.objects.select_related('customer', 'warehouse', 'created_by', 'approved_by'),
            pk=pk
        )
    items = sale.items.select_related('product').all()
    returns = sale.returns.select_related('customer').all()
    payments = sale.payments.all()

    context = {
        'sale': sale,
        'items': items,
        'returns': returns,
        'payments': payments,
        'reservation_status': sale.reservation_status,
        'outstanding': sale.outstanding_balance,
    }
    return render(request, 'sales/sale_detail.html', context)


# ============================================================
# SALE UPDATE
# ============================================================

@login_required
@never_cache
def sale_update(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(Sale, pk=pk, company=company)
    else:
        sale = get_object_or_404(Sale, pk=pk)

    if sale.status not in ('draft', 'confirmed'):
        messages.error(request, get_translation('sale_edit_status_error', lang))
        return redirect('sales:sale_detail', pk=pk)

    customers = Customer.objects.filter(company=company, is_active=True) if company else Customer.objects.filter(is_active=True)
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)
    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')
    existing_items = sale.items.select_related('product').all()

    if request.method == 'POST':
        with transaction.atomic():
            sale.customer_id = int(request.POST.get('customer', sale.customer_id))
            sale.warehouse_id = int(request.POST.get('warehouse', sale.warehouse_id))
            sale.expected_delivery_date = request.POST.get('expected_delivery_date') or sale.expected_delivery_date
            sale.payment_terms = request.POST.get('payment_terms', sale.payment_terms)
            sale.currency = request.POST.get('currency', sale.currency)
            sale.discount = Decimal(request.POST.get('discount', '0') or '0')
            sale.tax = Decimal(request.POST.get('tax', '0') or '0')
            sale.notes = request.POST.get('notes', sale.notes)
            sale.save()
            sale.items.all().delete()
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            discounts = request.POST.getlist('item_discounts')
            taxes = request.POST.getlist('item_taxes')
            for i, pid in enumerate(product_ids):
                if pid and quantities[i] and prices[i]:
                    SaleItem.objects.create(
                        sale=sale,
                        product_id=int(pid),
                        quantity=int(quantities[i]),
                        unit_price=Decimal(prices[i]),
                        discount=Decimal(discounts[i]) if i < len(discounts) and discounts[i] else Decimal('0'),
                        tax=Decimal(taxes[i]) if i < len(taxes) and taxes[i] else Decimal('0'),
                    )
        sale.calculate_total()

        Activity.log_activity(
            'product_updated',
            f"Sale {sale.reference} updated",
            user=request.user, company=company,
            related_object_type='Sale', related_object_id=sale.pk,
        )
        messages.success(request, get_translation('sale_updated', lang))
        return redirect('sales:sale_detail', pk=pk)

    return render(request, 'sales/sale_form.html', {
        'customers': customers, 'warehouses': warehouses, 'products': products,
        'sale': sale, 'items': existing_items,
        'payment_terms_choices': Sale.PAYMENT_TERMS_CHOICES,
        'currency_choices': Sale.CURRENCY_CHOICES,
    })


# ============================================================
# SALE DELETE
# ============================================================

@login_required
@never_cache
def sale_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(Sale, pk=pk, company=company)
    else:
        sale = get_object_or_404(Sale, pk=pk)

    if sale.status not in ('draft', 'cancelled'):
        messages.error(request, get_translation('sale_edit_status_error', lang))
        return redirect('sales:sale_detail', pk=pk)

    if request.method == 'POST':
        ref = sale.reference
        sale.delete()
        Activity.log_activity(
            'product_deleted',
            f"Sale {ref} deleted",
            user=request.user, company=company,
        )
        messages.success(request, get_translation('sale_deleted', lang))
        return redirect('sales:sale_list')

    return render(request, 'sales/sale_confirm_delete.html', {'sale': sale})


# ============================================================
# SALE STATUS UPDATE
# ============================================================

@login_required
@never_cache
def sale_update_status(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(Sale, pk=pk, company=company)
    else:
        sale = get_object_or_404(Sale, pk=pk)

    new_status = request.POST.get('status')
    if not new_status or not sale.can_transition(new_status):
        messages.error(request, get_translation('error', lang))
        return redirect('sales:sale_detail', pk=pk)

    try:
        with transaction.atomic():
            if new_status == 'completed':
                for item in sale.items.select_related('product').all():
                    qty_to_ship = item.quantity - item.shipped_quantity
                    if qty_to_ship > 0:
                        StockEngine.process_stock_change(
                            product=item.product,
                            warehouse=sale.warehouse,
                            company=company or sale.company,
                            direction='OUT',
                            movement_type='sale',
                            quantity=qty_to_ship,
                            user=request.user,
                            reference_type='Sale',
                            reference_id=sale.pk,
                            reference_number=sale.reference,
                            reason=f"Sale {sale.reference}: {item.product.name} x{qty_to_ship}",
                        )
                        item.shipped_quantity = item.quantity
                        item.save(update_fields=['shipped_quantity'])
                    if item.returned_quantity > 0:
                        item.returned_quantity = 0
                        item.save(update_fields=['returned_quantity'])

            elif new_status == 'cancelled':
                if sale.status == 'completed':
                    for item in sale.items.select_related('product').all():
                        if item.shipped_quantity > 0:
                            StockEngine.process_stock_change(
                                product=item.product,
                                warehouse=sale.warehouse,
                                company=company or sale.company,
                                direction='IN',
                                movement_type='sale_return',
                                quantity=item.shipped_quantity,
                                user=request.user,
                                reference_type='Sale',
                                reference_id=sale.pk,
                                reference_number=sale.reference,
                                reason=f"Sale {sale.reference} cancelled: {item.product.name} x{item.shipped_quantity}",
                            )
                            item.shipped_quantity = 0
                            item.reserved_quantity = 0
                            item.picked_quantity = 0
                            item.save(update_fields=['shipped_quantity', 'reserved_quantity', 'picked_quantity'])

            elif new_status == 'reserved':
                for item in sale.items.select_related('product').all():
                    available = StockEngine.get_available(item.product, company) if company else item.product.quantity
                    to_reserve = min(item.quantity, available)
                    item.reserved_quantity = to_reserve
                    item.save(update_fields=['reserved_quantity'])

            sale.transition_to(new_status)

        Activity.log_activity(
            'product_updated',
            f"Sale {sale.reference} status changed to {sale.get_status_display()}",
            user=request.user, company=company,
            related_object_type='Sale', related_object_id=sale.pk,
        )
        messages.success(request, get_translation('sale_updated', lang))
    except Exception as e:
        messages.error(request, str(e))

    return redirect('sales:sale_detail', pk=pk)


# ============================================================
# SALE RESERVE
# ============================================================

@login_required
@never_cache
def sale_reserve(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(Sale.objects.select_related('warehouse'), pk=pk, company=company)
    else:
        sale = get_object_or_404(Sale.objects.select_related('warehouse'), pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                for item in sale.items.select_related('product').all():
                    available = StockEngine.get_available(item.product, company) if company else item.product.quantity
                    to_reserve = min(item.available_to_reserve, available)
                    if to_reserve > 0:
                        StockEngine.process_stock_change(
                            product=item.product,
                            warehouse=sale.warehouse,
                            company=company or sale.company,
                            direction='OUT',
                            movement_type='sale',
                            quantity=to_reserve,
                            user=request.user,
                            reference_type='SaleReservation',
                            reference_id=sale.pk,
                            reference_number=sale.reference,
                            reason=f"Reserve for {sale.reference}: {item.product.name} x{to_reserve}",
                        )
                    item.reserved_quantity += to_reserve
                    item.save(update_fields=['reserved_quantity'])

            Activity.log_activity(
                'stock_out',
                f"Sale {sale.reference} stock reserved",
                user=request.user, company=company,
                related_object_type='Sale', related_object_id=sale.pk,
            )
            messages.success(request, get_translation('sale_updated', lang))
        except Exception as e:
            messages.error(request, str(e))

    return redirect('sales:sale_detail', pk=pk)


# ============================================================
# SALE PAYMENT
# ============================================================

@login_required
@never_cache
def sale_payment_create(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(Sale, pk=pk, company=company)
    else:
        sale = get_object_or_404(Sale, pk=pk)

    if request.method == 'POST':
        form = SalePaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.company = company or sale.company
            payment.sale = sale
            payment.created_by = request.user
            payment.save()

            Activity.log_activity(
                'product_added',
                f"Payment of {payment.amount} recorded for {sale.reference}",
                user=request.user, company=company,
                related_object_type='SalePayment', related_object_id=payment.pk,
            )
            messages.success(request, get_translation('sale_updated', lang))
        else:
            messages.error(request, get_translation('please_fill_required', lang))

    return redirect('sales:sale_detail', pk=pk)


# ============================================================
# SALE RETURN CREATE
# ============================================================

@login_required
@never_cache
def sale_return_create(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        sale = get_object_or_404(Sale.objects.select_related('customer', 'warehouse'), pk=pk, company=company)
    else:
        sale = get_object_or_404(Sale.objects.select_related('customer', 'warehouse'), pk=pk)

    shipped_items = sale.items.filter(shipped_quantity__gt=0).select_related('product')

    if request.method == 'POST':
        condition = request.POST.get('condition', 'sellable')
        movement_map = {
            'sellable': 'sale_return',
            'damaged': 'sale_return',
            'quarantine': 'sale_return',
            'inspection': 'sale_return',
        }
        movement_type = movement_map.get(condition, 'sale_return')

        return_order = SaleReturn.objects.create(
            company=company or sale.company,
            sale=sale,
            reference=_next_return_ref(company),
            customer=sale.customer,
            warehouse=sale.warehouse,
            reason=request.POST.get('reason', 'other'),
            reason_notes=request.POST.get('reason_notes', ''),
            condition=condition,
            notes=request.POST.get('notes', ''),
            created_by=request.user,
        )

        item_ids = request.POST.getlist('return_items')
        quantities = request.POST.getlist('return_quantities')
        for item_id, qty in zip(item_ids, quantities):
            if item_id and qty and int(qty) > 0:
                sale_item = SaleItem.objects.get(pk=int(item_id))
                return_qty = int(qty)

                SaleReturnItem.objects.create(
                    return_order=return_order,
                    sale_item=sale_item,
                    product=sale_item.product,
                    quantity=return_qty,
                    unit_price=sale_item.unit_price,
                )

                StockEngine.process_stock_change(
                    product=sale_item.product,
                    warehouse=sale.warehouse,
                    company=company or sale.company,
                    direction='IN',
                    movement_type=movement_type,
                    quantity=return_qty,
                    user=request.user,
                    reference_type='SaleReturn',
                    reference_id=return_order.pk,
                    reference_number=return_order.reference,
                    reason=f"Return from {sale.reference}: {sale_item.product.name} x{return_qty}",
                )

                sale_item.returned_quantity += return_qty
                sale_item.save(update_fields=['returned_quantity'])

        return_order.calculate_total()

        Activity.log_activity(
            'stock_in',
            f"Sale return {return_order.reference} created for {sale.reference}",
            user=request.user, company=company,
            related_object_type='SaleReturn', related_object_id=return_order.pk,
        )
        messages.success(request, get_translation('sale_created', lang))
        return redirect('sales:sale_detail', pk=pk)

    return render(request, 'sales/sale_return_form.html', {
        'sale': sale, 'shipped_items': shipped_items,
    })


# ============================================================
# SALE RETURN DETAIL
# ============================================================

@login_required
@never_cache
def sale_return_detail(request, pk):
    company = _get_company(request)
    if company:
        return_order = get_object_or_404(
            SaleReturn.objects.select_related('sale', 'customer', 'warehouse'),
            pk=pk, company=company
        )
    else:
        return_order = get_object_or_404(
            SaleReturn.objects.select_related('sale', 'customer', 'warehouse'),
            pk=pk
        )
    items = return_order.items.select_related('product', 'sale_item').all()
    return render(request, 'sales/sale_return_detail.html', {
        'return_order': return_order, 'items': items,
    })


# ============================================================
# SALE RETURN STATUS UPDATE
# ============================================================

@login_required
@never_cache
def sale_return_update_status(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        return_order = get_object_or_404(SaleReturn, pk=pk, company=company)
    else:
        return_order = get_object_or_404(SaleReturn, pk=pk)

    new_status = request.POST.get('status')
    if new_status in dict(SaleReturn.STATUS_CHOICES):
        return_order.status = new_status
        return_order.save(update_fields=['status', 'updated_at'])

        Activity.log_activity(
            'product_updated',
            f"Sale return {return_order.reference} status changed to {new_status}",
            user=request.user, company=company,
            related_object_type='SaleReturn', related_object_id=return_order.pk,
        )
        messages.success(request, get_translation('sale_updated', lang))

    return redirect('sales:sale_return_detail', pk=pk)


# ============================================================
# CUSTOMER LIST
# ============================================================

@login_required
@never_cache
def customer_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        customers = Customer.objects.filter(company=company)
    else:
        customers = Customer.objects.all()

    q = request.GET.get('q', '').strip()
    if q:
        customers = customers.filter(
            Q(name__icontains=q) |
            Q(contact_person__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q)
        )

    customers = customers.annotate(
        sales_cnt=Count('sales'),
        total_value=Sum('sales__total'),
    ).order_by('name')

    paginator = Paginator(customers, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sales/customer_list.html', {
        'page_obj': page_obj, 'q': q,
    })


# ============================================================
# CUSTOMER CREATE
# ============================================================

@login_required
@never_cache
def customer_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        return redirect('login')

    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.company = company
            customer.save()
            Activity.log_activity(
                'product_added',
                f"Customer {customer.name} created",
                user=request.user, company=company,
                related_object_type='Customer', related_object_id=customer.pk,
            )
            messages.success(request, get_translation('sale_created', lang))
            return redirect('sales:customer_list')
    else:
        form = CustomerForm()

    return render(request, 'sales/customer_form.html', {'form': form})


# ============================================================
# CUSTOMER DETAIL
# ============================================================

@login_required
@never_cache
def customer_detail(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=pk, company=company)
    else:
        customer = get_object_or_404(Customer, pk=pk)

    recent_sales = Sale.objects.filter(customer=customer).select_related('warehouse').order_by('-created_at')[:20]

    context = {
        'customer': customer,
        'recent_sales': recent_sales,
        'total_sales': customer.total_sales,
        'total_paid': customer.total_paid,
        'total_unpaid': customer.total_unpaid,
        'sale_count': customer.sale_count,
        'overdue_count': customer.overdue_count,
    }
    return render(request, 'sales/customer_detail.html', context)


# ============================================================
# CUSTOMER UPDATE
# ============================================================

@login_required
@never_cache
def customer_update(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=pk, company=company)
    else:
        customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            Activity.log_activity(
                'product_updated',
                f"Customer {customer.name} updated",
                user=request.user, company=company,
                related_object_type='Customer', related_object_id=customer.pk,
            )
            messages.success(request, get_translation('sale_updated', lang))
            return redirect('sales:customer_list')
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'sales/customer_form.html', {'form': form, 'customer': customer})


# ============================================================
# CUSTOMER DELETE
# ============================================================

@login_required
@never_cache
def customer_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=pk, company=company)
    else:
        customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        name = customer.name
        customer.delete()
        Activity.log_activity(
            'product_deleted',
            f"Customer {name} deleted",
            user=request.user, company=company,
        )
        messages.success(request, get_translation('sale_deleted', lang))
        return redirect('sales:customer_list')

    return render(request, 'sales/customer_confirm_delete.html', {'customer': customer})
