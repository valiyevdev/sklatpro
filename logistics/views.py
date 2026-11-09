from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F
from django.db import transaction
import json
from datetime import date, timedelta

from .models import (
    Driver, Vehicle, DeliveryZone, Route, RouteStop,
    Shipment, ShipmentPackage, ShipmentItem,
    Delivery, DeliveryStatusEvent, ShipmentTrackingEvent,
    DriverLocation, ProofOfDelivery, DeliveryCost,
    DeliveryReschedule, CourierProvider, DeliveryTimeWindow,
)
from .forms import (
    DriverForm, VehicleForm, RouteForm, RouteStopForm,
    ShipmentForm, ShipmentPackageForm, DeliveryForm,
    ProofOfDeliveryForm, DeliveryCostForm, DeliveryZoneForm,
    CourierProviderForm, DeliveryTimeWindowForm,
)


def _get_company(request):
    company = request.user.company
    if not company and not request.user.is_superuser:
        return None
    return company


def _lang(request):
    return getattr(request, 'LANGUAGE_CODE', 'en')


def _next_ref(company, prefix='SHP'):
    from logistics.models import Shipment
    last = Shipment.objects.filter(company=company).order_by('-pk').values_list('reference', flat=True).first()
    if last:
        try:
            num = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            num = Shipment.objects.filter(company=company).count() + 1
    else:
        num = 1
    return f'{prefix}-{num:06d}'


def _next_delivery_ref(company):
    last = Delivery.objects.filter(company=company).order_by('-pk').values_list('reference', flat=True).first()
    if last:
        try:
            num = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            num = Delivery.objects.filter(company=company).count() + 1
    else:
        num = 1
    return f'DLV-{num:06d}'


def _next_route_ref(company):
    last = Route.objects.filter(company=company).order_by('-pk').values_list('reference', flat=True).first()
    if last:
        try:
            num = int(last.split('-')[-1]) + 1
        except (ValueError, IndexError):
            num = Route.objects.filter(company=company).count() + 1
    else:
        num = 1
    return f'RT-{num:06d}'


def _paginate(request, qs, per_page=20):
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1
    total = qs.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    items = qs[start:start + per_page]
    return items, page, total, total_pages


# ─── LOGISTICS DASHBOARD ────────────────────────────────────────────

@login_required
@never_cache
def logistics_dashboard(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    today = date.today()
    shipments_qs = Shipment.objects.filter(company=company)
    deliveries_qs = Delivery.objects.filter(company=company)
    routes_qs = Route.objects.filter(company=company)
    drivers_qs = Driver.objects.filter(company=company, is_active=True)
    vehicles_qs = Vehicle.objects.filter(company=company, is_active=True)

    today_shipments = shipments_qs.filter(created_at__date=today).count()
    in_transit = shipments_qs.filter(status__in=['dispatched', 'in_transit', 'at_stop']).count()
    delivered_today = shipments_qs.filter(status='delivered', actual_delivery_at__date=today).count()
    failed_today = shipments_qs.filter(status='failed').count()
    unassigned = shipments_qs.filter(status='ready', driver__isnull=True).count()
    active_routes = routes_qs.filter(status__in=['started', 'in_progress']).count()
    available_drivers = drivers_qs.filter(status='available').count()
    available_vehicles = vehicles_qs.filter(status='available').count()

    today_deliveries = deliveries_qs.filter(created_at__date=today)
    delivery_stats = {
        'total': today_deliveries.count(),
        'delivered': today_deliveries.filter(status='delivered').count(),
        'failed': today_deliveries.filter(status='failed').count(),
        'in_transit': today_deliveries.filter(status__in=['dispatched', 'in_transit']).count(),
    }

    recent_shipments = shipments_qs.order_by('-created_at')[:10]
    active_deliveries = deliveries_qs.filter(
        status__in=['dispatched', 'in_transit', 'arrived']
    ).select_related('shipment', 'driver', 'customer')[:10]

    delayed = deliveries_qs.filter(
        expected_time__lt=timezone.now(),
        status__in=['pending', 'assigned', 'dispatched', 'in_transit']
    ).select_related('shipment', 'driver', 'customer')[:10]

    on_time_count = shipments_qs.filter(
        status='delivered',
        actual_delivery_at__isnull=False,
        expected_delivery_at__isnull=False,
        actual_delivery_at__lte=F('expected_delivery_at')
    ).count()
    completed_count = shipments_qs.filter(status='delivered').count()
    on_time_rate = round((on_time_count / completed_count * 100), 1) if completed_count > 0 else 0

    total_cost = DeliveryCost.objects.filter(company=company, cost_date=today).aggregate(
        total=Sum('amount'))['total'] or 0

    ctx = {
        'today_shipments': today_shipments,
        'in_transit': in_transit,
        'delivered_today': delivered_today,
        'failed_today': failed_today,
        'unassigned': unassigned,
        'active_routes': active_routes,
        'available_drivers': available_drivers,
        'available_vehicles': available_vehicles,
        'delivery_stats': delivery_stats,
        'recent_shipments': recent_shipments,
        'active_deliveries': active_deliveries,
        'delayed': delayed,
        'on_time_rate': on_time_rate,
        'total_cost_today': total_cost,
    }
    return render(request, 'logistics/dashboard.html', ctx)


# ─── SHIPMENTS ──────────────────────────────────────────────────────

@login_required
@never_cache
def shipment_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    qs = Shipment.objects.filter(company=company).select_related(
        'order', 'sale', 'customer', 'warehouse', 'driver', 'vehicle', 'route'
    )

    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    method = request.GET.get('method', '')
    driver_id = request.GET.get('driver', '')
    warehouse_id = request.GET.get('warehouse', '')

    if search:
        qs = qs.filter(
            Q(reference__icontains=search) |
            Q(tracking_number__icontains=search) |
            Q(carrier__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(delivery_address__icontains=search) |
            Q(delivery_contact_phone__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if method:
        qs = qs.filter(delivery_method=method)
    if driver_id:
        qs = qs.filter(driver_id=driver_id)
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)

    items, page, total, total_pages = _paginate(request, qs)

    drivers = Driver.objects.filter(company=company, is_active=True)
    warehouses = None
    try:
        from warehouses.models import Warehouse
        warehouses = Warehouse.objects.filter(company=company)
    except Exception:
        pass

    ctx = {
        'shipments': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'search': search,
        'status': status,
        'priority': priority,
        'method': method,
        'driver_id': driver_id,
        'warehouse_id': warehouse_id,
        'status_choices': Shipment.STATUS_CHOICES,
        'priority_choices': Shipment.PRIORITY_CHOICES,
        'method_choices': Shipment.METHOD_CHOICES,
        'drivers': drivers,
        'warehouses': warehouses,
    }
    return render(request, 'logistics/shipment_list.html', ctx)


@login_required
@never_cache
def shipment_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = ShipmentForm(request.POST)
        if form.is_valid():
            shipment = form.save(commit=False)
            shipment.company = company
            shipment.created_by = request.user
            if not shipment.reference:
                shipment.reference = _next_ref(company)
            shipment.save()
            messages.success(request, 'Shipment created successfully.')
            return redirect('logistics:shipment_detail', pk=shipment.pk)
    else:
        form = ShipmentForm(initial={'reference': _next_ref(company), 'status': 'draft', 'priority': 'normal', 'delivery_method': 'own_vehicle'})

    drivers = Driver.objects.filter(company=company, is_active=True)
    vehicles = Vehicle.objects.filter(company=company, is_active=True)
    try:
        from warehouses.models import Warehouse
        warehouses = Warehouse.objects.filter(company=company)
    except Exception:
        warehouses = []

    from sales.models import Customer
    customers = Customer.objects.filter(company=company)
    from orders.models import Order
    orders = Order.objects.filter(company=company)

    ctx = {
        'form': form,
        'drivers': drivers,
        'vehicles': vehicles,
        'warehouses': warehouses,
        'customers': customers,
        'orders': orders,
    }
    return render(request, 'logistics/shipment_form.html', ctx)


@login_required
@never_cache
def shipment_detail(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)
    packages = shipment.packages.all()
    items = shipment.items.all()
    tracking = shipment.tracking_events.all()
    costs = shipment.costs.all()
    deliveries = shipment.deliveries.all()
    proofs = ProofOfDelivery.objects.filter(delivery__shipment=shipment)

    from django.contrib.contenttypes.models import ContentType
    from activity.models import Activity
    activities = Activity.objects.filter(
        related_object_type=ContentType.objects.get_for_model(Shipment).model,
        related_object_id=shipment.pk
    ).order_by('-created_at')[:20]

    ctx = {
        'shipment': shipment,
        'packages': packages,
        'items': items,
        'tracking': tracking,
        'costs': costs,
        'deliveries': deliveries,
        'proofs': proofs,
        'activities': activities,
    }
    return render(request, 'logistics/shipment_detail.html', ctx)


@login_required
@never_cache
def shipment_update(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)

    if request.method == 'POST':
        form = ShipmentForm(request.POST, instance=shipment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shipment updated successfully.')
            return redirect('logistics:shipment_detail', pk=shipment.pk)
    else:
        form = ShipmentForm(instance=shipment)

    ctx = {'form': form, 'shipment': shipment}
    return render(request, 'logistics/shipment_form.html', ctx)


@login_required
@never_cache
def shipment_update_status(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        valid = dict(Shipment.STATUS_CHOICES).keys()
        if new_status in valid:
            old_status = shipment.status
            shipment.status = new_status

            if new_status == 'dispatched':
                shipment.actual_dispatch_at = timezone.now()
            elif new_status == 'delivered':
                shipment.actual_delivery_at = timezone.now()

            shipment.save()

            ShipmentTrackingEvent.objects.create(
                company=company,
                shipment=shipment,
                event_type=f'status_changed',
                description=f'{old_status} → {new_status}',
                created_by=request.user,
            )

            try:
                from activity.models import Activity
                Activity.log_activity(
                    'shipment_status_changed',
                    f'Shipment {shipment.reference}: {old_status} → {new_status}',
                    user=request.user,
                    company=company,
                    related_object_type='logistics.shipment',
                    related_object_id=shipment.pk,
                )
            except Exception:
                pass

            messages.success(request, f'Shipment status updated to {new_status}.')

    return redirect('logistics:shipment_detail', pk=pk)


@login_required
@never_cache
def shipment_delete(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)

    if request.method == 'POST':
        ref = shipment.reference
        shipment.delete()
        messages.success(request, f'Shipment {ref} deleted.')
        return redirect('logistics:shipment_list')

    return render(request, 'logistics/shipment_confirm_delete.html', {'shipment': shipment})


@login_required
@never_cache
def shipment_add_package(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)

    if request.method == 'POST':
        form = ShipmentPackageForm(request.POST)
        if form.is_valid():
            pkg = form.save(commit=False)
            pkg.company = company
            pkg.shipment = shipment
            if not pkg.package_number:
                pkg.package_number = f'PKG-{shipment.packages.count() + 1:03d}'
            pkg.save()
            shipment.total_packages = shipment.packages.aggregate(s=Sum('quantity'))['s'] or shipment.packages.count()
            shipment.total_weight_kg = shipment.packages.aggregate(s=Sum('weight_kg'))['s'] or 0
            shipment.save()
            messages.success(request, 'Package added.')
    else:
        form = ShipmentPackageForm()

    return redirect('logistics:shipment_detail', pk=pk)


# ─── DELIVERIES ─────────────────────────────────────────────────────

@login_required
@never_cache
def delivery_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    qs = Delivery.objects.filter(company=company).select_related(
        'shipment', 'driver', 'vehicle', 'customer'
    )

    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    driver_id = request.GET.get('driver', '')

    if search:
        qs = qs.filter(
            Q(reference__icontains=search) |
            Q(shipment__reference__icontains=search) |
            Q(customer__name__icontains=search) |
            Q(contact_phone__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if driver_id:
        qs = qs.filter(driver_id=driver_id)

    items, page, total, total_pages = _paginate(request, qs)
    drivers = Driver.objects.filter(company=company, is_active=True)

    ctx = {
        'deliveries': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'search': search,
        'status': status,
        'driver_id': driver_id,
        'status_choices': Delivery.STATUS_CHOICES,
        'drivers': drivers,
    }
    return render(request, 'logistics/delivery_list.html', ctx)


@login_required
@never_cache
def delivery_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = DeliveryForm(request.POST)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.company = company
            delivery.created_by = request.user
            if not delivery.reference:
                delivery.reference = _next_delivery_ref(company)
            delivery.save()
            messages.success(request, 'Delivery created.')
            return redirect('logistics:delivery_detail', pk=delivery.pk)
    else:
        form = DeliveryForm(initial={
            'reference': _next_delivery_ref(company),
            'status': 'pending',
        })

    ctx = {'form': form}
    return render(request, 'logistics/delivery_form.html', ctx)


@login_required
@never_cache
def delivery_detail(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    delivery = get_object_or_404(Delivery, pk=pk, company=company)
    events = delivery.status_events.all()
    proofs = delivery.proofs_of_delivery.all()
    reschedules = delivery.reschedules.all()

    ctx = {
        'delivery': delivery,
        'events': events,
        'proofs': proofs,
        'reschedules': reschedules,
    }
    return render(request, 'logistics/delivery_detail.html', ctx)


@login_required
@never_cache
def delivery_update_status(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    delivery = get_object_or_404(Delivery, pk=pk, company=company)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        failure_reason = request.POST.get('failure_reason', '')
        failure_notes = request.POST.get('failure_notes', '')
        delivered_qty = request.POST.get('delivered_quantity', '')

        valid = dict(Delivery.STATUS_CHOICES).keys()
        if new_status in valid:
            old_status = delivery.status
            delivery.status = new_status

            if new_status == 'arrived':
                delivery.actual_arrival = timezone.now()
            elif new_status in ['delivered', 'partially_delivered']:
                if delivered_qty:
                    delivery.delivered_quantity = int(delivered_qty)
                delivery.actual_departure = timezone.now()
            elif new_status == 'failed':
                delivery.failure_reason = failure_reason
                delivery.failure_notes = failure_notes

            delivery.save()

            DeliveryStatusEvent.objects.create(
                company=company,
                delivery=delivery,
                from_status=old_status,
                to_status=new_status,
                notes=failure_notes if new_status == 'failed' else '',
                created_by=request.user,
            )

            if new_status in ['delivered', 'partially_delivered'] and delivery.shipment:
                shipment = delivery.shipment
                delivered_total = shipment.deliveries.filter(
                    status__in=['delivered', 'partially_delivered']
                ).aggregate(s=Sum('delivered_quantity'))['s'] or 0

                if delivered_total >= shipment.items.aggregate(s=Sum('ordered_quantity'))['s']:
                    shipment.status = 'delivered'
                    shipment.actual_delivery_at = timezone.now()
                else:
                    shipment.status = 'partially_delivered'
                shipment.save()

            if new_status == 'failed' and delivery.shipment:
                delivery.shipment.status = 'failed'
                delivery.shipment.save()

            try:
                from activity.models import Activity
                Activity.log_activity(
                    'delivery_status_changed',
                    f'Delivery {delivery.reference}: {old_status} → {new_status}',
                    user=request.user,
                    company=company,
                    related_object_type='logistics.delivery',
                    related_object_id=delivery.pk,
                )
            except Exception:
                pass

            messages.success(request, f'Delivery status updated to {new_status}.')

    return redirect('logistics:delivery_detail', pk=pk)


@login_required
@never_cache
def delivery_reschedule(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    delivery = get_object_or_404(Delivery, pk=pk, company=company)

    if request.method == 'POST':
        new_time = request.POST.get('new_expected_time', '')
        reason = request.POST.get('reason', '')

        from django.utils.dateparse import parse_datetime
        parsed_time = parse_datetime(new_time) if new_time else None

        DeliveryReschedule.objects.create(
            company=company,
            delivery=delivery,
            old_expected_time=delivery.expected_time,
            new_expected_time=parsed_time,
            reason=reason,
            changed_by=request.user,
        )

        if parsed_time:
            delivery.expected_time = parsed_time
        delivery.status = 'rescheduled'
        delivery.save()

        messages.success(request, 'Delivery rescheduled.')
        return redirect('logistics:delivery_detail', pk=pk)

    return render(request, 'logistics/delivery_reschedule.html', {'delivery': delivery})


@login_required
@never_cache
def delivery_return(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    delivery = get_object_or_404(Delivery, pk=pk, company=company)

    if request.method == 'POST':
        delivery.status = 'returned'
        delivery.save()

        DeliveryStatusEvent.objects.create(
            company=company,
            delivery=delivery,
            from_status=delivery.status,
            to_status='returned',
            notes='Returned to warehouse',
            created_by=request.user,
        )

        if delivery.shipment:
            delivery.shipment.status = 'returned'
            delivery.shipment.save()

        messages.success(request, 'Delivery marked as returned to warehouse.')
        return redirect('logistics:delivery_detail', pk=pk)

    return render(request, 'logistics/delivery_confirm_return.html', {'delivery': delivery})


# ─── DRIVERS ────────────────────────────────────────────────────────

@login_required
@never_cache
def driver_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    qs = Driver.objects.filter(company=company)
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(license_number__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)

    items, page, total, total_pages = _paginate(request, qs)

    ctx = {
        'drivers': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'search': search,
        'status': status,
        'status_choices': Driver.STATUS_CHOICES,
    }
    return render(request, 'logistics/driver_list.html', ctx)


@login_required
@never_cache
def driver_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = DriverForm(request.POST)
        if form.is_valid():
            driver = form.save(commit=False)
            driver.company = company
            driver.save()
            messages.success(request, 'Driver added.')
            return redirect('logistics:driver_detail', pk=driver.pk)
    else:
        form = DriverForm()

    return render(request, 'logistics/driver_form.html', {'form': form})


@login_required
@never_cache
def driver_detail(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    driver = get_object_or_404(Driver, pk=pk, company=company)
    routes = driver.routes.all().order_by('-route_date')[:10]
    shipments = driver.shipments.all().order_by('-created_at')[:10]
    deliveries = driver.deliveries.all().order_by('-created_at')[:10]

    delivery_stats = driver.deliveries.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status='delivered')),
        failed=Count('id', filter=Q(status='failed')),
    )
    completed = delivery_stats['delivered'] or 0
    total_del = delivery_stats['total'] or 0
    on_time_rate = round((completed / total_del * 100), 1) if total_del > 0 else 0

    ctx = {
        'driver': driver,
        'routes': routes,
        'shipments': shipments,
        'deliveries': deliveries,
        'delivery_stats': delivery_stats,
        'on_time_rate': on_time_rate,
    }
    return render(request, 'logistics/driver_detail.html', ctx)


@login_required
@never_cache
def driver_update(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    driver = get_object_or_404(Driver, pk=pk, company=company)

    if request.method == 'POST':
        form = DriverForm(request.POST, instance=driver)
        if form.is_valid():
            form.save()
            messages.success(request, 'Driver updated.')
            return redirect('logistics:driver_detail', pk=pk)
    else:
        form = DriverForm(instance=driver)

    return render(request, 'logistics/driver_form.html', {'form': form, 'driver': driver})


@login_required
@never_cache
def driver_delete(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    driver = get_object_or_404(Driver, pk=pk, company=company)

    if request.method == 'POST':
        driver.delete()
        messages.success(request, 'Driver deleted.')
        return redirect('logistics:driver_list')

    return render(request, 'logistics/driver_confirm_delete.html', {'driver': driver})


@login_required
@never_cache
def driver_update_status(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    driver = get_object_or_404(Driver, pk=pk, company=company)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        valid = dict(Driver.STATUS_CHOICES).keys()
        if new_status in valid:
            driver.status = new_status
            driver.save()
            messages.success(request, f'Driver status updated to {new_status}.')

    return redirect('logistics:driver_detail', pk=pk)


# ─── VEHICLES ───────────────────────────────────────────────────────

@login_required
@never_cache
def vehicle_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    qs = Vehicle.objects.filter(company=company)
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    vtype = request.GET.get('type', '')

    if search:
        qs = qs.filter(
            Q(vehicle_number__icontains=search) |
            Q(plate_number__icontains=search) |
            Q(brand__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if vtype:
        qs = qs.filter(vehicle_type=vtype)

    items, page, total, total_pages = _paginate(request, qs)

    ctx = {
        'vehicles': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'search': search,
        'status': status,
        'vtype': vtype,
        'status_choices': Vehicle.STATUS_CHOICES,
        'type_choices': Vehicle.TYPE_CHOICES,
    }
    return render(request, 'logistics/vehicle_list.html', ctx)


@login_required
@never_cache
def vehicle_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.company = company
            vehicle.save()
            messages.success(request, 'Vehicle added.')
            return redirect('logistics:vehicle_detail', pk=vehicle.pk)
    else:
        form = VehicleForm()

    drivers = Driver.objects.filter(company=company, is_active=True)
    return render(request, 'logistics/vehicle_form.html', {'form': form, 'drivers': drivers})


@login_required
@never_cache
def vehicle_detail(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    vehicle = get_object_or_404(Vehicle, pk=pk, company=company)
    routes = vehicle.routes.all().order_by('-route_date')[:10]
    active_deliveries = vehicle.deliveries.filter(
        status__in=['dispatched', 'in_transit', 'arrived']
    ).select_related('shipment', 'customer')[:10]

    ctx = {
        'vehicle': vehicle,
        'routes': routes,
        'active_deliveries': active_deliveries,
    }
    return render(request, 'logistics/vehicle_detail.html', ctx)


@login_required
@never_cache
def vehicle_update(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    vehicle = get_object_or_404(Vehicle, pk=pk, company=company)

    if request.method == 'POST':
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle updated.')
            return redirect('logistics:vehicle_detail', pk=pk)
    else:
        form = VehicleForm(instance=vehicle)

    drivers = Driver.objects.filter(company=company, is_active=True)
    return render(request, 'logistics/vehicle_form.html', {'form': form, 'vehicle': vehicle, 'drivers': drivers})


@login_required
@never_cache
def vehicle_delete(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    vehicle = get_object_or_404(Vehicle, pk=pk, company=company)

    if request.method == 'POST':
        vehicle.delete()
        messages.success(request, 'Vehicle deleted.')
        return redirect('logistics:vehicle_list')

    return render(request, 'logistics/vehicle_confirm_delete.html', {'vehicle': vehicle})


# ─── ROUTES ─────────────────────────────────────────────────────────

@login_required
@never_cache
def route_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    qs = Route.objects.filter(company=company).select_related('driver', 'vehicle', 'warehouse')
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    if search:
        qs = qs.filter(
            Q(reference__icontains=search) |
            Q(driver__first_name__icontains=search) |
            Q(driver__last_name__icontains=search) |
            Q(vehicle__vehicle_number__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)

    items, page, total, total_pages = _paginate(request, qs)

    ctx = {
        'routes': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'search': search,
        'status': status,
        'status_choices': Route.STATUS_CHOICES,
    }
    return render(request, 'logistics/route_list.html', ctx)


@login_required
@never_cache
def route_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = RouteForm(request.POST)
        if form.is_valid():
            route = form.save(commit=False)
            route.company = company
            route.created_by = request.user
            if not route.reference:
                route.reference = _next_route_ref(company)
            route.save()
            messages.success(request, 'Route created.')
            return redirect('logistics:route_detail', pk=route.pk)
    else:
        form = RouteForm(initial={'reference': _next_route_ref(company), 'status': 'draft', 'route_date': date.today()})

    drivers = Driver.objects.filter(company=company, is_active=True)
    vehicles = Vehicle.objects.filter(company=company, is_active=True)
    try:
        from warehouses.models import Warehouse
        warehouses = Warehouse.objects.filter(company=company)
    except Exception:
        warehouses = []

    ctx = {'form': form, 'drivers': drivers, 'vehicles': vehicles, 'warehouses': warehouses}
    return render(request, 'logistics/route_form.html', ctx)


@login_required
@never_cache
def route_detail(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    route = get_object_or_404(Route, pk=pk, company=company)
    stops = route.stops.select_related('customer').all()
    shipments = route.shipments.all()
    costs = route.costs.all()

    ctx = {
        'route': route,
        'stops': stops,
        'shipments': shipments,
        'costs': costs,
    }
    return render(request, 'logistics/route_detail.html', ctx)


@login_required
@never_cache
def route_update(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    route = get_object_or_404(Route, pk=pk, company=company)

    if request.method == 'POST':
        form = RouteForm(request.POST, instance=route)
        if form.is_valid():
            form.save()
            messages.success(request, 'Route updated.')
            return redirect('logistics:route_detail', pk=pk)
    else:
        form = RouteForm(instance=route)

    drivers = Driver.objects.filter(company=company, is_active=True)
    vehicles = Vehicle.objects.filter(company=company, is_active=True)
    try:
        from warehouses.models import Warehouse
        warehouses = Warehouse.objects.filter(company=company)
    except Exception:
        warehouses = []

    ctx = {'form': form, 'route': route, 'drivers': drivers, 'vehicles': vehicles, 'warehouses': warehouses}
    return render(request, 'logistics/route_form.html', ctx)


@login_required
@never_cache
def route_update_status(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    route = get_object_or_404(Route, pk=pk, company=company)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        valid = dict(Route.STATUS_CHOICES).keys()
        if new_status in valid:
            old_status = route.status
            route.status = new_status

            if new_status == 'started':
                route.actual_start = timezone.now().time()
            elif new_status == 'completed':
                route.actual_end = timezone.now().time()

            route.save()

            if new_status == 'started' and route.driver:
                route.driver.status = 'on_route'
                route.driver.save()
            elif new_status == 'completed' and route.driver:
                route.driver.status = 'available'
                route.driver.save()

            if new_status == 'started' and route.vehicle:
                route.vehicle.status = 'on_route'
                route.vehicle.save()
            elif new_status == 'completed' and route.vehicle:
                route.vehicle.status = 'available'
                route.vehicle.save()

            messages.success(request, f'Route status updated to {new_status}.')

    return redirect('logistics:route_detail', pk=pk)


@login_required
@never_cache
def route_add_stop(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    route = get_object_or_404(Route, pk=pk, company=company)

    if request.method == 'POST':
        form = RouteStopForm(request.POST)
        if form.is_valid():
            stop = form.save(commit=False)
            stop.company = company
            stop.route = route
            if not stop.sequence:
                stop.sequence = route.stops.count() + 1
            stop.save()
            messages.success(request, 'Stop added.')
    else:
        form = RouteStopForm(initial={'sequence': route.stops.count() + 1})

    return redirect('logistics:route_detail', pk=pk)


@login_required
@never_cache
def route_stop_delete(request, route_pk, stop_pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    stop = get_object_or_404(RouteStop, pk=stop_pk, route__pk=route_pk, company=company)
    stop.delete()
    messages.success(request, 'Stop removed.')
    return redirect('logistics:route_detail', pk=route_pk)


@login_required
@never_cache
def route_stop_update_status(request, route_pk, stop_pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    stop = get_object_or_404(RouteStop, pk=stop_pk, route__pk=route_pk, company=company)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        valid = dict(RouteStop.STATUS_CHOICES).keys()
        if new_status in valid:
            old_status = stop.status
            stop.status = new_status
            if new_status == 'completed':
                stop.actual_arrival = timezone.now().time()
                stop.actual_departure = timezone.now().time()
            elif new_status == 'in_progress':
                stop.actual_arrival = timezone.now().time()
            stop.save()

    return redirect('logistics:route_detail', pk=route_pk)


# ─── DISPATCH BOARD ─────────────────────────────────────────────────

@login_required
@never_cache
def dispatch_board(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    unassigned_shipments = Shipment.objects.filter(
        company=company, status='ready', driver__isnull=True
    ).select_related('customer', 'warehouse')

    available_drivers = Driver.objects.filter(
        company=company, status='available', is_active=True
    )
    available_vehicles = Vehicle.objects.filter(
        company=company, status='available', is_active=True
    )

    active_routes = Route.objects.filter(
        company=company, status__in=['started', 'in_progress']
    ).select_related('driver', 'vehicle')

    active_deliveries = Delivery.objects.filter(
        company=company, status__in=['dispatched', 'in_transit', 'arrived']
    ).select_related('shipment', 'driver', 'customer')

    delayed_deliveries = Delivery.objects.filter(
        company=company,
        expected_time__lt=timezone.now(),
        status__in=['pending', 'assigned', 'dispatched', 'in_transit']
    ).select_related('shipment', 'driver', 'customer')

    failed_deliveries = Delivery.objects.filter(
        company=company, status='failed'
    ).select_related('shipment', 'driver', 'customer')[:10]

    ctx = {
        'unassigned_shipments': unassigned_shipments,
        'available_drivers': available_drivers,
        'available_vehicles': available_vehicles,
        'active_routes': active_routes,
        'active_deliveries': active_deliveries,
        'delayed_deliveries': delayed_deliveries,
        'failed_deliveries': failed_deliveries,
    }
    return render(request, 'logistics/dispatch_board.html', ctx)


@login_required
@never_cache
def dispatch_assign(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        shipment_id = request.POST.get('shipment_id')
        driver_id = request.POST.get('driver_id')
        vehicle_id = request.POST.get('vehicle_id')
        route_id = request.POST.get('route_id')

        shipment = get_object_or_404(Shipment, pk=shipment_id, company=company)
        driver = get_object_or_404(Driver, pk=driver_id, company=company) if driver_id else None
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, company=company) if vehicle_id else None
        route = get_object_or_404(Route, pk=route_id, company=company) if route_id else None

        if driver:
            shipment.driver = driver
            driver.status = 'assigned'
            driver.save()
        if vehicle:
            if vehicle.max_weight_kg and shipment.total_weight_kg > vehicle.max_weight_kg:
                messages.warning(request, f'Warning: Shipment weight ({shipment.total_weight_kg}kg) exceeds vehicle capacity ({vehicle.max_weight_kg}kg).')
            if vehicle.max_volume_m3 and shipment.total_volume_m3 > vehicle.max_volume_m3:
                messages.warning(request, f'Warning: Shipment volume ({shipment.total_volume_m3}m3) exceeds vehicle capacity ({vehicle.max_volume_m3}m3).')
            shipment.vehicle = vehicle
            vehicle.status = 'assigned'
            vehicle.save()
        if route:
            shipment.route = route

        shipment.status = 'assigned'
        shipment.save()

        ShipmentTrackingEvent.objects.create(
            company=company,
            shipment=shipment,
            event_type='assigned',
            description=f'Assigned to {driver} / {vehicle}',
            created_by=request.user,
        )

        try:
            from activity.models import Activity
            Activity.log_activity(
                'shipment_assigned',
                f'Shipment {shipment.reference} assigned to driver {driver}',
                user=request.user,
                company=company,
                related_object_type='logistics.shipment',
                related_object_id=shipment.pk,
            )
        except Exception:
            pass

        messages.success(request, 'Shipment assigned successfully.')

    return redirect('logistics:dispatch_board')


@login_required
@never_cache
def dispatch_reassign(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        shipment_id = request.POST.get('shipment_id')
        driver_id = request.POST.get('driver_id')
        vehicle_id = request.POST.get('vehicle_id')

        shipment = get_object_or_404(Shipment, pk=shipment_id, company=company)

        if shipment.driver:
            shipment.driver.status = 'available'
            shipment.driver.save()
        if shipment.vehicle:
            shipment.vehicle.status = 'available'
            shipment.vehicle.save()

        driver = get_object_or_404(Driver, pk=driver_id, company=company) if driver_id else None
        vehicle = get_object_or_404(Vehicle, pk=vehicle_id, company=company) if vehicle_id else None

        if driver:
            shipment.driver = driver
            driver.status = 'assigned'
            driver.save()
        if vehicle:
            shipment.vehicle = vehicle
            vehicle.status = 'assigned'
            vehicle.save()

        shipment.save()
        messages.success(request, 'Shipment reassigned.')

    return redirect('logistics:dispatch_board')


# ─── TRACKING ───────────────────────────────────────────────────────

@login_required
@never_cache
def tracking_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    search = request.GET.get('q', '').strip()
    qs = Shipment.objects.filter(company=company)

    if search:
        qs = qs.filter(
            Q(reference__icontains=search) |
            Q(tracking_number__icontains=search)
        )

    items, page, total, total_pages = _paginate(request, qs)

    ctx = {
        'shipments': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'search': search,
    }
    return render(request, 'logistics/tracking_list.html', ctx)


@login_required
@never_cache
def tracking_detail(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)
    events = shipment.tracking_events.all()

    ctx = {
        'shipment': shipment,
        'events': events,
    }
    return render(request, 'logistics/tracking_detail.html', ctx)


@login_required
@never_cache
def tracking_add_event(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipment = get_object_or_404(Shipment, pk=pk, company=company)

    if request.method == 'POST':
        event_type = request.POST.get('event_type', '')
        description = request.POST.get('description', '')

        ShipmentTrackingEvent.objects.create(
            company=company,
            shipment=shipment,
            event_type=event_type,
            description=description,
            created_by=request.user,
        )
        messages.success(request, 'Tracking event added.')

    return redirect('logistics:tracking_detail', pk=pk)


# ─── PROOF OF DELIVERY ─────────────────────────────────────────────

@login_required
@never_cache
def pod_capture(request, delivery_pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    delivery = get_object_or_404(Delivery, pk=delivery_pk, company=company)

    if request.method == 'POST':
        form = ProofOfDeliveryForm(request.POST, request.FILES)
        if form.is_valid():
            pod = form.save(commit=False)
            pod.company = company
            pod.delivery = delivery
            pod.captured_by = request.user
            pod.captured_at = timezone.now()
            pod.status = 'captured'
            pod.save()
            messages.success(request, 'Proof of delivery captured.')
            return redirect('logistics:delivery_detail', pk=delivery.pk)
    else:
        form = ProofOfDeliveryForm()

    ctx = {'form': form, 'delivery': delivery}
    return render(request, 'logistics/pod_capture.html', ctx)


@login_required
@never_cache
def pod_verify(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    pod = get_object_or_404(ProofOfDelivery, pk=pk, company=company)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'verify':
            pod.status = 'verified'
            pod.verified_at = timezone.now()
            pod.save()
            messages.success(request, 'Proof verified.')
        elif action == 'reject':
            pod.status = 'rejected'
            pod.save()
            messages.warning(request, 'Proof rejected.')

    return redirect('logistics:delivery_detail', pk=pod.delivery.pk)


# ─── DELIVERY COSTS ────────────────────────────────────────────────

@login_required
@never_cache
def cost_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    qs = DeliveryCost.objects.filter(company=company).select_related('shipment', 'route', 'delivery')
    category = request.GET.get('category', '')
    if category:
        qs = qs.filter(category=category)

    items, page, total, total_pages = _paginate(request, qs)
    total_amount = qs.aggregate(s=Sum('amount'))['s'] or 0

    ctx = {
        'costs': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'category': category,
        'category_choices': DeliveryCost.CATEGORY_CHOICES,
        'total_amount': total_amount,
    }
    return render(request, 'logistics/cost_list.html', ctx)


@login_required
@never_cache
def cost_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = DeliveryCostForm(request.POST)
        if form.is_valid():
            cost = form.save(commit=False)
            cost.company = company
            cost.created_by = request.user
            cost.save()

            try:
                from finance.models import FinancialTransaction, ExpenseCategory, FinancialAccount
                account = FinancialAccount.objects.filter(company=company, account_type='cash').first()
                expense_cat = ExpenseCategory.objects.filter(company=company, name__icontains='delivery').first()
                if not expense_cat:
                    expense_cat = ExpenseCategory.objects.filter(company=company).first()

                if account and expense_cat:
                    txn = FinancialTransaction.objects.create(
                        company=company,
                        date=cost.cost_date,
                        txn_type='expense',
                        direction='out',
                        amount=cost.amount,
                        account=account,
                        description=f'Delivery cost: {cost.get_category_display()} - {cost.description}',
                    )
                    cost.finance_transaction = txn
                    cost.save()
            except Exception:
                pass

            messages.success(request, 'Delivery cost recorded.')
            return redirect('logistics:cost_list')
    else:
        form = DeliveryCostForm(initial={'cost_date': date.today(), 'currency': 'UZS'})

    ctx = {'form': form}
    return render(request, 'logistics/cost_form.html', ctx)


@login_required
@never_cache
def cost_delete(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    cost = get_object_or_404(DeliveryCost, pk=pk, company=company)

    if request.method == 'POST':
        cost.delete()
        messages.success(request, 'Cost record deleted.')
        return redirect('logistics:cost_list')

    return render(request, 'logistics/cost_confirm_delete.html', {'cost': cost})


# ─── LOGISTICS REPORTS ──────────────────────────────────────────────

@login_required
@never_cache
def logistics_reports(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    today = date.today()
    month_start = today.replace(day=1)

    shipments = Shipment.objects.filter(company=company)
    deliveries = Delivery.objects.filter(company=company)
    costs = DeliveryCost.objects.filter(company=company)

    shipment_stats = {
        'total': shipments.count(),
        'draft': shipments.filter(status='draft').count(),
        'ready': shipments.filter(status='ready').count(),
        'assigned': shipments.filter(status='assigned').count(),
        'dispatched': shipments.filter(status='dispatched').count(),
        'in_transit': shipments.filter(status='in_transit').count(),
        'delivered': shipments.filter(status='delivered').count(),
        'failed': shipments.filter(status='failed').count(),
        'returned': shipments.filter(status='returned').count(),
    }

    completed = shipments.filter(status='delivered')
    on_time = completed.filter(
        actual_delivery_at__isnull=False,
        expected_delivery_at__isnull=False,
        actual_delivery_at__lte=F('expected_delivery_at')
    ).count()
    completed_count = completed.count()

    delivery_stats = {
        'total': deliveries.count(),
        'delivered': deliveries.filter(status='delivered').count(),
        'failed': deliveries.filter(status='failed').count(),
    }

    driver_stats = Driver.objects.filter(company=company, is_active=True).annotate(
        total_deliveries=Count('deliveries'),
        completed_deliveries=Count('deliveries', filter=Q(deliveries__status='delivered')),
        failed_deliveries=Count('deliveries', filter=Q(deliveries__status='failed')),
    ).order_by('-completed_deliveries')[:10]

    vehicle_stats = Vehicle.objects.filter(company=company, is_active=True).annotate(
        total_routes=Count('routes'),
        total_deliveries=Count('deliveries'),
    ).order_by('-total_deliveries')[:10]

    cost_by_category = costs.values('category').annotate(
        total=Sum('amount')
    ).order_by('-total')

    total_cost = costs.aggregate(s=Sum('amount'))['s'] or 0

    month_cost = costs.filter(cost_date__gte=month_start).aggregate(s=Sum('amount'))['s'] or 0

    avg_cost_per_delivery = 0
    delivered_count = delivery_stats['delivered']
    if delivered_count > 0:
        avg_cost_per_delivery = round(float(total_cost) / delivered_count, 2)

    ctx = {
        'shipment_stats': shipment_stats,
        'on_time_rate': round((on_time / completed_count * 100), 1) if completed_count > 0 else 0,
        'on_time_count': on_time,
        'completed_count': completed_count,
        'delivery_stats': delivery_stats,
        'driver_stats': driver_stats,
        'vehicle_stats': vehicle_stats,
        'cost_by_category': cost_by_category,
        'total_cost': total_cost,
        'month_cost': month_cost,
        'avg_cost_per_delivery': avg_cost_per_delivery,
    }
    return render(request, 'logistics/reports.html', ctx)


# ─── DRIVER MOBILE WORKSPACE ───────────────────────────────────────

@login_required
@never_cache
def driver_mobile(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    today = date.today()
    try:
        driver = Driver.objects.get(company=company, user=request.user)
    except Driver.DoesNotExist:
        messages.warning(request, 'No driver profile found for your account.')
        return redirect('logistics:logistics_dashboard')

    today_routes = Route.objects.filter(
        company=company, driver=driver, route_date=today
    ).order_by('planned_start')

    today_deliveries = Delivery.objects.filter(
        company=company, driver=driver,
        created_at__date=today,
        status__in=['assigned', 'dispatched', 'in_transit', 'arrived', 'pending']
    ).select_related('shipment', 'customer').order_by('expected_time')

    next_stop = today_deliveries.filter(
        status__in=['assigned', 'dispatched', 'in_transit']
    ).first()

    completed_today = Delivery.objects.filter(
        company=company, driver=driver,
        created_at__date=today,
        status__in=['delivered', 'partially_delivered']
    ).count()

    ctx = {
        'driver': driver,
        'today_routes': today_routes,
        'today_deliveries': today_deliveries,
        'next_stop': next_stop,
        'completed_today': completed_today,
    }
    return render(request, 'logistics/driver_mobile.html', ctx)


@login_required
@never_cache
def driver_mobile_update_status(request, delivery_pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    delivery = get_object_or_404(Delivery, pk=delivery_pk, company=company)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'arrived':
            delivery.status = 'arrived'
            delivery.actual_arrival = timezone.now()
            delivery.save()
            DeliveryStatusEvent.objects.create(
                company=company, delivery=delivery,
                from_status='in_transit', to_status='arrived',
                created_by=request.user,
            )
        elif action == 'delivered':
            qty = request.POST.get('delivered_quantity', '')
            if qty:
                delivery.delivered_quantity = int(qty)
            delivery.status = 'delivered'
            delivery.actual_departure = timezone.now()
            delivery.save()
            DeliveryStatusEvent.objects.create(
                company=company, delivery=delivery,
                from_status='arrived', to_status='delivered',
                created_by=request.user,
            )
        elif action == 'partial':
            qty = request.POST.get('delivered_quantity', '')
            if qty:
                delivery.delivered_quantity = int(qty)
            delivery.status = 'partially_delivered'
            delivery.actual_departure = timezone.now()
            delivery.save()
            DeliveryStatusEvent.objects.create(
                company=company, delivery=delivery,
                from_status='arrived', to_status='partially_delivered',
                created_by=request.user,
            )
        elif action == 'failed':
            delivery.status = 'failed'
            delivery.failure_reason = request.POST.get('failure_reason', 'other')
            delivery.failure_notes = request.POST.get('failure_notes', '')
            delivery.save()
            DeliveryStatusEvent.objects.create(
                company=company, delivery=delivery,
                from_status=delivery.status, to_status='failed',
                notes=delivery.failure_notes,
                created_by=request.user,
            )

    return redirect('logistics:driver_mobile')


# ─── DRIVER LOCATION ───────────────────────────────────────────────

@login_required
@never_cache
def driver_location_update(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('latitude')
            lng = data.get('longitude')
            accuracy = data.get('accuracy')
            speed = data.get('speed')
            heading = data.get('heading')
            route_id = data.get('route_id')

            if lat and lng:
                try:
                    driver = Driver.objects.get(company=company, user=request.user)
                except Driver.DoesNotExist:
                    return JsonResponse({'error': 'No driver profile'}, status=400)

                route = None
                if route_id:
                    route = Route.objects.filter(pk=route_id, company=company).first()

                DriverLocation.objects.create(
                    driver=driver,
                    latitude=lat,
                    longitude=lng,
                    accuracy=accuracy,
                    speed=speed,
                    heading=heading,
                    route=route,
                )
                return JsonResponse({'status': 'ok'})
        except Exception:
            pass

    return JsonResponse({'error': 'Invalid request'}, status=400)


# ─── DELIVERY ZONES ────────────────────────────────────────────────

@login_required
@never_cache
def zone_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    zones = DeliveryZone.objects.filter(company=company)
    return render(request, 'logistics/zone_list.html', {'zones': zones})


@login_required
@never_cache
def zone_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = DeliveryZoneForm(request.POST)
        if form.is_valid():
            zone = form.save(commit=False)
            zone.company = company
            zone.save()
            messages.success(request, 'Delivery zone created.')
            return redirect('logistics:zone_list')
    else:
        form = DeliveryZoneForm()

    return render(request, 'logistics/zone_form.html', {'form': form})


@login_required
@never_cache
def zone_update(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    zone = get_object_or_404(DeliveryZone, pk=pk, company=company)

    if request.method == 'POST':
        form = DeliveryZoneForm(request.POST, instance=zone)
        if form.is_valid():
            form.save()
            messages.success(request, 'Zone updated.')
            return redirect('logistics:zone_list')
    else:
        form = DeliveryZoneForm(instance=zone)

    return render(request, 'logistics/zone_form.html', {'form': form, 'zone': zone})


# ─── COURIER PROVIDERS ─────────────────────────────────────────────

@login_required
@never_cache
def courier_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    couriers = CourierProvider.objects.filter(company=company)
    return render(request, 'logistics/courier_list.html', {'couriers': couriers})


@login_required
@never_cache
def courier_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = CourierProviderForm(request.POST)
        if form.is_valid():
            courier = form.save(commit=False)
            courier.company = company
            courier.save()
            messages.success(request, 'Courier provider added.')
            return redirect('logistics:courier_list')
    else:
        form = CourierProviderForm()

    return render(request, 'logistics/courier_form.html', {'form': form})


@login_required
@never_cache
def courier_update(request, pk):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    courier = get_object_or_404(CourierProvider, pk=pk, company=company)

    if request.method == 'POST':
        form = CourierProviderForm(request.POST, instance=courier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Courier provider updated.')
            return redirect('logistics:courier_list')
    else:
        form = CourierProviderForm(instance=courier)

    return render(request, 'logistics/courier_form.html', {'form': form, 'courier': courier})


# ─── TIME WINDOWS ──────────────────────────────────────────────────

@login_required
@never_cache
def time_window_list(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    windows = DeliveryTimeWindow.objects.filter(company=company)
    return render(request, 'logistics/time_window_list.html', {'windows': windows})


@login_required
@never_cache
def time_window_create(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    if request.method == 'POST':
        form = DeliveryTimeWindowForm(request.POST)
        if form.is_valid():
            tw = form.save(commit=False)
            tw.company = company
            tw.save()
            messages.success(request, 'Time window created.')
            return redirect('logistics:time_window_list')
    else:
        form = DeliveryTimeWindowForm()

    return render(request, 'logistics/time_window_form.html', {'form': form})


# ─── EXPORT ─────────────────────────────────────────────────────────

@login_required
@never_cache
def shipment_export(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    shipments = Shipment.objects.filter(company=company).select_related('customer', 'driver', 'vehicle')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="shipments_{date.today()}.csv"'

    import csv
    writer = csv.writer(response)
    writer.writerow([
        'Reference', 'Customer', 'Address', 'Status', 'Priority',
        'Driver', 'Vehicle', 'Tracking Number', 'Carrier',
        'Created', 'Dispatched', 'Delivered'
    ])

    for s in shipments:
        writer.writerow([
            s.reference,
            str(s.customer) if s.customer else '',
            s.delivery_address,
            s.get_status_display(),
            s.get_priority_display(),
            str(s.driver) if s.driver else '',
            str(s.vehicle) if s.vehicle else '',
            s.tracking_number,
            s.carrier,
            s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else '',
            s.actual_dispatch_at.strftime('%Y-%m-%d %H:%M') if s.actual_dispatch_at else '',
            s.actual_delivery_at.strftime('%Y-%m-%d %H:%M') if s.actual_delivery_at else '',
        ])

    return response


@login_required
@never_cache
def delivery_export(request):
    company = _get_company(request)
    if not company:
        return redirect('users:profile')

    deliveries = Delivery.objects.filter(company=company).select_related('shipment', 'driver', 'customer')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="deliveries_{date.today()}.csv"'

    import csv
    writer = csv.writer(response)
    writer.writerow([
        'Reference', 'Shipment', 'Customer', 'Address', 'Status',
        'Driver', 'Ordered', 'Delivered', 'Failure Reason',
        'Expected', 'Actual Arrival', 'Actual Departure'
    ])

    for d in deliveries:
        writer.writerow([
            d.reference,
            d.shipment.reference if d.shipment else '',
            str(d.customer) if d.customer else '',
            d.delivery_address,
            d.get_status_display(),
            str(d.driver) if d.driver else '',
            d.ordered_quantity,
            d.delivered_quantity,
            d.failure_reason,
            d.expected_time.strftime('%Y-%m-%d %H:%M') if d.expected_time else '',
            d.actual_arrival.strftime('%Y-%m-%d %H:%M') if d.actual_arrival else '',
            d.actual_departure.strftime('%Y-%m-%d %H:%M') if d.actual_departure else '',
        ])

    return response
