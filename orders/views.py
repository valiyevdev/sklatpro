from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from .models import Order, OrderItem, OrderPayment
from .forms import OrderForm, OrderItemForm, OrderPaymentForm
from sales.models import Customer
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


def _next_ref(company, prefix='ORD'):
    if company:
        count = Order.objects.filter(company=company).count()
    else:
        count = Order.objects.count()
    return f"{prefix}-{count + 1:04d}"


# ============================================================
# ORDER DASHBOARD
# ============================================================

@login_required
@never_cache
def order_dashboard(request):
    company = _get_company(request)
    lang = _lang(request)

    if company:
        orders = Order.objects.filter(company=company)
        customers = Customer.objects.filter(company=company)
    else:
        orders = Order.objects.all()
        customers = Customer.objects.all()

    today = timezone.now().date()
    month_start = today.replace(day=1)

    context = {
        'orders_today': orders.filter(created_at__date=today).count(),
        'orders_month': orders.filter(created_at__date__gte=month_start).count(),
        'pending_count': orders.filter(status='pending').count(),
        'confirmed_count': orders.filter(status='confirmed').count(),
        'reserved_count': orders.filter(status='reserved').count(),
        'processing_count': orders.filter(status__in=['processing', 'picking', 'packing']).count(),
        'backordered_count': orders.filter(status='backordered').count(),
        'ready_to_ship': orders.filter(status='ready_to_ship').count(),
        'shipped_count': orders.filter(status='shipped').count(),
        'delivered_count': orders.filter(status='delivered').count(),
        'cancelled_count': orders.filter(status='cancelled').count(),
        'overdue_payments': orders.filter(payment_status='overdue').count(),
        'top_customers': customers.annotate(
            orders_cnt=Count('orders'),
            total_value=Sum('orders__total'),
        ).order_by('-total_value')[:5],
        'recent_orders': orders.select_related('customer', 'warehouse').order_by('-created_at')[:10],
    }
    return render(request, 'orders/order_dashboard.html', context)


# ============================================================
# ORDER LIST
# ============================================================

@login_required
@never_cache
def order_list(request):
    company = _get_company(request)
    lang = _lang(request)
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if company:
        orders = Order.objects.filter(company=company).select_related('customer', 'warehouse', 'created_by')
    else:
        orders = Order.objects.select_related('customer', 'warehouse', 'created_by').all()

    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    payment_filter = request.GET.get('payment_status', '')
    priority_filter = request.GET.get('priority', '')
    customer_filter = request.GET.get('customer', '')
    warehouse_filter = request.GET.get('warehouse', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if q:
        orders = orders.filter(
            Q(reference__icontains=q) |
            Q(customer__name__icontains=q) |
            Q(items__product__name__icontains=q) |
            Q(items__product__sku__icontains=q)
        ).distinct()
    if status_filter:
        orders = orders.filter(status=status_filter)
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)
    if priority_filter:
        orders = orders.filter(priority=priority_filter)
    if customer_filter:
        orders = orders.filter(customer_id=customer_filter)
    if warehouse_filter:
        orders = orders.filter(warehouse_id=warehouse_filter)
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)

    orders = orders.order_by('-created_at')
    paginator = Paginator(orders, 20)
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
        'priority_filter': priority_filter,
        'customer_filter': customer_filter,
        'warehouse_filter': warehouse_filter,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': Order.STATUS_CHOICES,
        'payment_choices': Order.PAYMENT_STATUS_CHOICES,
        'priority_choices': Order.PRIORITY_CHOICES,
        'total_count': paginator.count,
    }
    return render(request, 'orders/order_list.html', context)


# ============================================================
# ORDER CREATE
# ============================================================

@login_required
@never_cache
def order_create(request):
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
            order = Order.objects.create(
                company=company,
                reference=_next_ref(company),
                customer_id=int(customer_id),
                warehouse_id=int(warehouse_id),
                expected_delivery_date=request.POST.get('expected_delivery_date') or None,
                priority=request.POST.get('priority', 'normal'),
                payment_terms=request.POST.get('payment_terms', 'cod'),
                currency=request.POST.get('currency', 'UZS'),
                discount=Decimal(request.POST.get('discount', '0') or '0'),
                tax=Decimal(request.POST.get('tax', '0') or '0'),
                delivery_address=request.POST.get('delivery_address', ''),
                delivery_phone=request.POST.get('delivery_phone', ''),
                delivery_method=request.POST.get('delivery_method', ''),
                internal_notes=request.POST.get('internal_notes', ''),
                customer_notes=request.POST.get('customer_notes', ''),
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
                        OrderItem.objects.create(
                            order=order,
                            product_id=int(pid),
                            quantity=qty,
                            unit_price=Decimal(prices[i]),
                            discount=Decimal(discounts[i]) if i < len(discounts) and discounts[i] else Decimal('0'),
                            tax=Decimal(taxes[i]) if i < len(taxes) and taxes[i] else Decimal('0'),
                        )
            order.calculate_total()

            Activity.log_activity(
                'product_added',
                f"Order {order.reference} created",
                user=request.user, company=company,
                related_object_type='Order', related_object_id=order.pk,
            )
            messages.success(request, get_translation('order_created', lang))
            return redirect('orders:order_detail', pk=order.pk)
        messages.error(request, get_translation('please_fill_required', lang))

    return render(request, 'orders/order_form.html', {
        'customers': customers, 'warehouses': warehouses, 'products': products,
        'payment_terms_choices': Order.PAYMENT_TERMS_CHOICES,
        'currency_choices': [('UZS', 'UZS'), ('USD', 'USD')],
    })


# ============================================================
# ORDER DETAIL
# ============================================================

@login_required
@never_cache
def order_detail(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(
            Order.objects.select_related('customer', 'warehouse', 'created_by'),
            pk=pk, company=company
        )
    else:
        order = get_object_or_404(
            Order.objects.select_related('customer', 'warehouse', 'created_by'),
            pk=pk
        )
    items = order.items.select_related('product').all()
    payments = order.payments.all()

    timeline = []
    status_changes = Activity.objects.filter(
        related_object_type='Order',
        related_object_id=order.pk,
    ).order_by('-created_at')[:20]
    for act in status_changes:
        timeline.append({
            'description': act.description,
            'user': act.user,
            'created_at': act.created_at,
        })

    context = {
        'order': order,
        'items': items,
        'payments': payments,
        'timeline': timeline,
        'reservation_status': order.reservation_status,
        'fulfillment_percentage': order.fulfillment_percentage,
        'outstanding': order.outstanding_balance,
    }
    return render(request, 'orders/order_detail.html', context)


# ============================================================
# ORDER UPDATE
# ============================================================

@login_required
@never_cache
def order_update(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(Order, pk=pk, company=company)
    else:
        order = get_object_or_404(Order, pk=pk)

    if order.status not in ('draft', 'pending'):
        messages.error(request, get_translation('order_edit_status_error', lang))
        return redirect('orders:order_detail', pk=pk)

    customers = Customer.objects.filter(company=company, is_active=True) if company else Customer.objects.filter(is_active=True)
    warehouses = Warehouse.objects.filter(company=company, is_active=True) if company else Warehouse.objects.filter(is_active=True)
    products = Product.objects.filter(company=company).order_by('name') if company else Product.objects.all().order_by('name')
    existing_items = order.items.select_related('product').all()

    if request.method == 'POST':
        with transaction.atomic():
            order.customer_id = int(request.POST.get('customer', order.customer_id))
            order.warehouse_id = int(request.POST.get('warehouse', order.warehouse_id))
            order.expected_delivery_date = request.POST.get('expected_delivery_date') or order.expected_delivery_date
            order.priority = request.POST.get('priority', order.priority)
            order.payment_terms = request.POST.get('payment_terms', order.payment_terms)
            order.currency = request.POST.get('currency', order.currency)
            order.discount = Decimal(request.POST.get('discount', '0') or '0')
            order.tax = Decimal(request.POST.get('tax', '0') or '0')
            order.delivery_address = request.POST.get('delivery_address', order.delivery_address)
            order.delivery_phone = request.POST.get('delivery_phone', order.delivery_phone)
            order.delivery_method = request.POST.get('delivery_method', order.delivery_method)
            order.internal_notes = request.POST.get('internal_notes', order.internal_notes)
            order.customer_notes = request.POST.get('customer_notes', order.customer_notes)
            order.notes = request.POST.get('notes', order.notes)
            order.save()
            order.items.all().delete()
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            prices = request.POST.getlist('prices')
            discounts = request.POST.getlist('item_discounts')
            taxes = request.POST.getlist('item_taxes')
            for i, pid in enumerate(product_ids):
                if pid and quantities[i] and prices[i]:
                    OrderItem.objects.create(
                        order=order,
                        product_id=int(pid),
                        quantity=int(quantities[i]),
                        unit_price=Decimal(prices[i]),
                        discount=Decimal(discounts[i]) if i < len(discounts) and discounts[i] else Decimal('0'),
                        tax=Decimal(taxes[i]) if i < len(taxes) and taxes[i] else Decimal('0'),
                    )
        order.calculate_total()

        Activity.log_activity(
            'product_updated',
            f"Order {order.reference} updated",
            user=request.user, company=company,
            related_object_type='Order', related_object_id=order.pk,
        )
        messages.success(request, get_translation('order_updated', lang))
        return redirect('orders:order_detail', pk=pk)

    return render(request, 'orders/order_form.html', {
        'customers': customers, 'warehouses': warehouses, 'products': products,
        'order': order, 'items': existing_items,
        'payment_terms_choices': Order.PAYMENT_TERMS_CHOICES,
        'currency_choices': [('UZS', 'UZS'), ('USD', 'USD')],
    })


# ============================================================
# ORDER DELETE
# ============================================================

@login_required
@never_cache
def order_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(Order, pk=pk, company=company)
    else:
        order = get_object_or_404(Order, pk=pk)

    if order.status not in ('draft', 'cancelled'):
        messages.error(request, get_translation('order_edit_status_error', lang))
        return redirect('orders:order_detail', pk=pk)

    if request.method == 'POST':
        ref = order.reference
        order.delete()
        Activity.log_activity(
            'product_deleted',
            f"Order {ref} deleted",
            user=request.user, company=company,
        )
        messages.success(request, get_translation('order_deleted', lang))
        return redirect('orders:order_list')

    return render(request, 'orders/order_confirm_delete.html', {'order': order})


# ============================================================
# ORDER STATUS UPDATE
# ============================================================

@login_required
@never_cache
def order_update_status(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(Order, pk=pk, company=company)
    else:
        order = get_object_or_404(Order, pk=pk)

    new_status = request.POST.get('status')
    if not new_status or not order.can_transition(new_status):
        messages.error(request, get_translation('invalid_status_transition', lang))
        return redirect('orders:order_detail', pk=pk)

    try:
        with transaction.atomic():
            if new_status == 'reserved':
                for item in order.items.select_related('product').all():
                    available = StockEngine.get_available(item.product, company) if company else item.product.quantity
                    to_reserve = min(item.quantity, available)
                    item.reserved_quantity = to_reserve
                    item.save(update_fields=['reserved_quantity'])

            elif new_status == 'completed':
                for item in order.items.select_related('product').all():
                    qty_to_ship = item.quantity - item.shipped_quantity
                    if qty_to_ship > 0:
                        StockEngine.process_stock_change(
                            product=item.product,
                            warehouse=order.warehouse,
                            company=company or order.company,
                            direction='OUT',
                            movement_type='sale',
                            quantity=qty_to_ship,
                            user=request.user,
                            reference_type='Order',
                            reference_id=order.pk,
                            reference_number=order.reference,
                            reason=f"Order {order.reference}: {item.product.name} x{qty_to_ship}",
                        )
                        item.shipped_quantity = item.quantity
                        item.save(update_fields=['shipped_quantity'])

            elif new_status == 'cancelled':
                if order.status == 'completed':
                    for item in order.items.select_related('product').all():
                        if item.shipped_quantity > 0:
                            StockEngine.process_stock_change(
                                product=item.product,
                                warehouse=order.warehouse,
                                company=company or order.company,
                                direction='IN',
                                movement_type='sale_return',
                                quantity=item.shipped_quantity,
                                user=request.user,
                                reference_type='Order',
                                reference_id=order.pk,
                                reference_number=order.reference,
                                reason=f"Order {order.reference} cancelled: {item.product.name} x{item.shipped_quantity}",
                            )
                            item.shipped_quantity = 0
                            item.reserved_quantity = 0
                            item.picked_quantity = 0
                            item.save(update_fields=['shipped_quantity', 'reserved_quantity', 'picked_quantity'])

            order.transition_to(new_status)

        Activity.log_activity(
            'product_updated',
            f"Order {order.reference} status changed to {order.get_status_display()}",
            user=request.user, company=company,
            related_object_type='Order', related_object_id=order.pk,
        )
        messages.success(request, get_translation('order_updated', lang))
    except Exception as e:
        messages.error(request, str(e))

    return redirect('orders:order_detail', pk=pk)


# ============================================================
# ORDER RESERVE
# ============================================================

@login_required
@never_cache
def order_reserve(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(Order.objects.select_related('warehouse'), pk=pk, company=company)
    else:
        order = get_object_or_404(Order.objects.select_related('warehouse'), pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                for item in order.items.select_related('product').all():
                    available = StockEngine.get_available(item.product, company) if company else item.product.quantity
                    remaining = item.quantity - item.reserved_quantity
                    to_reserve = min(remaining, available)
                    if to_reserve > 0:
                        item.reserved_quantity += to_reserve
                        item.save(update_fields=['reserved_quantity'])

            Activity.log_activity(
                'stock_out',
                f"Order {order.reference} stock reserved",
                user=request.user, company=company,
                related_object_type='Order', related_object_id=order.pk,
            )
            messages.success(request, get_translation('order_updated', lang))
        except Exception as e:
            messages.error(request, str(e))

    return redirect('orders:order_detail', pk=pk)


# ============================================================
# ORDER PAYMENT
# ============================================================

@login_required
@never_cache
def order_payment_create(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(Order, pk=pk, company=company)
    else:
        order = get_object_or_404(Order, pk=pk)

    if request.method == 'POST':
        form = OrderPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.company = company or order.company
            payment.order = order
            payment.created_by = request.user
            payment.save()

            Activity.log_activity(
                'product_added',
                f"Payment of {payment.amount} recorded for {order.reference}",
                user=request.user, company=company,
                related_object_type='OrderPayment', related_object_id=payment.pk,
            )
            messages.success(request, get_translation('order_updated', lang))
        else:
            messages.error(request, get_translation('please_fill_required', lang))

    return redirect('orders:order_detail', pk=pk)


# ============================================================
# ORDER DUPLICATE
# ============================================================

@login_required
@never_cache
def order_duplicate(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        original = get_object_or_404(Order.objects.select_related('customer', 'warehouse'), pk=pk, company=company)
    else:
        original = get_object_or_404(Order.objects.select_related('customer', 'warehouse'), pk=pk)

    if request.method == 'POST':
        new_order = Order.objects.create(
            company=company or original.company,
            reference=_next_ref(company),
            customer=original.customer,
            warehouse=original.warehouse,
            expected_delivery_date=original.expected_delivery_date,
            priority=original.priority,
            payment_terms=original.payment_terms,
            currency=original.currency,
            discount=original.discount,
            tax=original.tax,
            delivery_address=original.delivery_address,
            delivery_phone=original.delivery_phone,
            delivery_method=original.delivery_method,
            notes=original.notes,
            created_by=request.user,
        )

        original_items = original.items.select_related('product').all()
        with transaction.atomic():
            for item in original_items:
                OrderItem.objects.create(
                    order=new_order,
                    product=item.product,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    discount=item.discount,
                    tax=item.tax,
                )
        new_order.calculate_total()

        Activity.log_activity(
            'product_added',
            f"Order {new_order.reference} duplicated from {original.reference}",
            user=request.user, company=company,
            related_object_type='Order', related_object_id=new_order.pk,
        )
        messages.success(request, get_translation('order_created', lang))
        return redirect('orders:order_detail', pk=new_order.pk)

    return redirect('orders:order_detail', pk=pk)


# ============================================================
# ORDER FULFILLMENT UPDATE
# ============================================================

@login_required
@never_cache
def order_update_fulfillment(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        order = get_object_or_404(Order, pk=pk, company=company)
    else:
        order = get_object_or_404(Order, pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                item_ids = request.POST.getlist('item_ids')
                for item_id in item_ids:
                    item = OrderItem.objects.get(pk=int(item_id), order=order)
                    picked = int(request.POST.get(f'picked_{item_id}', item.picked_quantity) or item.picked_quantity)
                    packed = int(request.POST.get(f'packed_{item_id}', item.packed_quantity) or item.packed_quantity)
                    shipped = int(request.POST.get(f'shipped_{item_id}', item.shipped_quantity) or item.shipped_quantity)
                    delivered = int(request.POST.get(f'delivered_{item_id}', item.delivered_quantity) or item.delivered_quantity)
                    returned = int(request.POST.get(f'returned_{item_id}', item.returned_quantity) or item.returned_quantity)
                    backordered = int(request.POST.get(f'backordered_{item_id}', item.backordered_quantity) or item.backordered_quantity)

                    item.picked_quantity = picked
                    item.packed_quantity = packed
                    item.shipped_quantity = shipped
                    item.delivered_quantity = delivered
                    item.returned_quantity = returned
                    item.backordered_quantity = backordered
                    item.save(update_fields=[
                        'picked_quantity', 'packed_quantity', 'shipped_quantity',
                        'delivered_quantity', 'returned_quantity', 'backordered_quantity',
                    ])

            Activity.log_activity(
                'product_updated',
                f"Order {order.reference} fulfillment updated",
                user=request.user, company=company,
                related_object_type='Order', related_object_id=order.pk,
            )
            messages.success(request, get_translation('order_updated', lang))
        except Exception as e:
            messages.error(request, str(e))

    return redirect('orders:order_detail', pk=pk)
