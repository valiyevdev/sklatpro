from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from datetime import timedelta
from products.models import Product
from inventory.models import StockEngine, StockLevel, StockMovement
from core.translations import get_translation
from .models import *
from .forms import *


def _lang(request):
    return request.session.get('language', 'uz')


def _get_company(request):
    company = request.user.company
    if not company and not request.user.is_superuser:
        return None
    return company


def _company_qs(model, company):
    if company:
        return model.objects.filter(company=company)
    return model.objects.all()


def _next_ref(company, prefix, model, padding=4):
    if company:
        count = model.objects.filter(company=company).count()
    else:
        count = model.objects.count()
    return f"{prefix}-{count + 1:0{padding}d}"


def _paginate(request, qs, per_page=20):
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


def _get_products(company):
    if company:
        return Product.objects.filter(company=company)
    return Product.objects.all()


def _get_warehouses(company):
    if company:
        return Warehouse.objects.filter(company=company)
    return Warehouse.objects.all()


def _get_locations(company):
    if company:
        return Location.objects.filter(company=company)
    return Location.objects.all()


def _get_users(company):
    from users.models import User
    if company:
        return User.objects.filter(company=company)
    return User.objects.all()


@login_required
@never_cache
def warehouse_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    warehouses = Warehouse.objects.filter(company=company) if company else Warehouse.objects.all()
    q = request.GET.get('q', '').strip()
    if q:
        warehouses = warehouses.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(city__icontains=q)
        )
    warehouses = warehouses.order_by('name')
    page = _paginate(request, warehouses)
    return render(request, 'warehouses/warehouse_list.html', {
        'warehouses': page,
        'q': q,
        'lang': lang,
    })


@login_required
@never_cache
def warehouse_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = WarehouseForm(request.POST, company=company)
        if form.is_valid():
            wh = form.save(commit=False)
            wh.company = company
            if not wh.code:
                wh.code = _next_ref(company, 'WH', Warehouse)[:12]
            wh.save()
            messages.success(request, get_translation('warehouse_created', lang))
            return redirect('warehouses:warehouse_list')
    else:
        form = WarehouseForm(company=company)
    return render(request, 'warehouses/warehouse_form.html', {
        'form': form,
        'form_type': 'create',
        'lang': lang,
    })


@login_required
@never_cache
def warehouse_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    zones = warehouse.zones.filter(is_active=True)
    locations = warehouse.locations.filter(is_active=True)
    stock_levels = StockLevel.objects.filter(
        company=company, warehouse=warehouse
    ).select_related('product').order_by('-quantity')[:50]
    total_stock = stock_levels.aggregate(s=Sum('quantity'))['s'] or 0
    batches = Batch.objects.filter(company=company, warehouse=warehouse, status='active')
    return render(request, 'warehouses/warehouse_detail.html', {
        'warehouse': warehouse,
        'zones': zones,
        'locations': locations,
        'stock_levels': stock_levels,
        'total_stock': total_stock,
        'batches': batches,
        'lang': lang,
    })


@login_required
@never_cache
def warehouse_update(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == 'POST':
        form = WarehouseForm(request.POST, instance=warehouse, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('warehouse_updated', lang))
            return redirect('warehouses:warehouse_detail', pk=pk)
    else:
        form = WarehouseForm(instance=warehouse, company=company)
    return render(request, 'warehouses/warehouse_form.html', {
        'form': form,
        'form_type': 'update',
        'warehouse': warehouse,
        'lang': lang,
    })


@login_required
@never_cache
def warehouse_delete(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    if request.method == 'POST':
        warehouse.delete()
        messages.success(request, get_translation('warehouse_deleted', lang))
        return redirect('warehouses:warehouse_list')
    return render(request, 'warehouses/warehouse_confirm_delete.html', {
        'warehouse': warehouse,
        'lang': lang,
    })


@login_required
@never_cache
def zone_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    zones = Zone.objects.filter(company=company) if company else Zone.objects.all()
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        zones = zones.filter(warehouse_id=warehouse_id)
    zones = zones.select_related('warehouse').order_by('code')
    page = _paginate(request, zones)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/zone_list.html', {
        'zones': page,
        'warehouses': warehouses,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def zone_create(request, warehouse_id=None):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = ZoneForm(request.POST, company=company)
        if form.is_valid():
            zone = form.save(commit=False)
            zone.company = company
            zone.save()
            messages.success(request, get_translation('zone_created', lang))
            return redirect('warehouses:zone_detail', pk=zone.pk)
    else:
        initial = {}
        if warehouse_id:
            initial['warehouse'] = warehouse_id
        form = ZoneForm(company=company, initial=initial)
    return render(request, 'warehouses/zone_form.html', {
        'form': form,
        'form_type': 'create',
        'lang': lang,
    })


@login_required
@never_cache
def zone_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    zone = get_object_or_404(Zone, pk=pk, company=company)
    locations = zone.locations.filter(is_active=True).order_by('code')
    return render(request, 'warehouses/zone_detail.html', {
        'zone': zone,
        'locations': locations,
        'lang': lang,
    })


@login_required
@never_cache
def zone_update(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    zone = get_object_or_404(Zone, pk=pk, company=company)
    if request.method == 'POST':
        form = ZoneForm(request.POST, instance=zone, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('zone_updated', lang))
            return redirect('warehouses:zone_detail', pk=pk)
    else:
        form = ZoneForm(instance=zone, company=company)
    return render(request, 'warehouses/zone_form.html', {
        'form': form,
        'form_type': 'update',
        'zone': zone,
        'lang': lang,
    })


@login_required
@never_cache
def zone_delete(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    zone = get_object_or_404(Zone, pk=pk, company=company)
    if request.method == 'POST':
        warehouse_pk = zone.warehouse_id
        zone.delete()
        messages.success(request, get_translation('zone_deleted', lang))
        return redirect('warehouses:warehouse_detail', pk=warehouse_pk)
    return render(request, 'warehouses/zone_confirm_delete.html', {
        'zone': zone,
        'lang': lang,
    })


@login_required
@never_cache
def location_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    locations = Location.objects.filter(company=company) if company else Location.objects.all()
    warehouse_id = request.GET.get('warehouse')
    zone_id = request.GET.get('zone')
    q = request.GET.get('q', '').strip()
    if warehouse_id:
        locations = locations.filter(warehouse_id=warehouse_id)
    if zone_id:
        locations = locations.filter(zone_id=zone_id)
    if q:
        locations = locations.filter(
            Q(name__icontains=q) | Q(code__icontains=q) | Q(barcode__icontains=q)
        )
    locations = locations.select_related('warehouse', 'zone').order_by('code')
    page = _paginate(request, locations)
    warehouses = _get_warehouses(company)
    zones = Zone.objects.filter(company=company) if company else Zone.objects.all()
    return render(request, 'warehouses/location_list.html', {
        'locations': page,
        'warehouses': warehouses,
        'zones': zones,
        'selected_warehouse': warehouse_id,
        'selected_zone': zone_id,
        'q': q,
        'lang': lang,
    })


@login_required
@never_cache
def location_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = LocationForm(request.POST, company=company)
        if form.is_valid():
            loc = form.save(commit=False)
            loc.company = company
            loc.save()
            messages.success(request, get_translation('location_created', lang))
            return redirect('warehouses:location_detail', pk=loc.pk)
    else:
        initial = {}
        warehouse_id = request.GET.get('warehouse')
        zone_id = request.GET.get('zone')
        if warehouse_id:
            initial['warehouse'] = warehouse_id
        if zone_id:
            initial['zone'] = zone_id
        form = LocationForm(company=company, initial=initial)
    return render(request, 'warehouses/location_form.html', {
        'form': form,
        'form_type': 'create',
        'lang': lang,
    })


@login_required
@never_cache
def location_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    location = get_object_or_404(Location, pk=pk, company=company)
    stock_levels = StockLocation.objects.filter(
        company=company, location=location
    ).select_related('product').order_by('-quantity')
    return render(request, 'warehouses/location_detail.html', {
        'location': location,
        'stock_levels': stock_levels,
        'lang': lang,
    })


@login_required
@never_cache
def location_update(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    location = get_object_or_404(Location, pk=pk, company=company)
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('location_updated', lang))
            return redirect('warehouses:location_detail', pk=pk)
    else:
        form = LocationForm(instance=location, company=company)
    return render(request, 'warehouses/location_form.html', {
        'form': form,
        'form_type': 'update',
        'location': location,
        'lang': lang,
    })


@login_required
@never_cache
def location_delete(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    location = get_object_or_404(Location, pk=pk, company=company)
    if request.method == 'POST':
        warehouse_pk = location.warehouse_id
        location.delete()
        messages.success(request, get_translation('location_deleted', lang))
        return redirect('warehouses:warehouse_detail', pk=warehouse_pk)
    return render(request, 'warehouses/location_confirm_delete.html', {
        'location': location,
        'lang': lang,
    })


@login_required
@never_cache
def receiving_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = Receiving.objects.filter(company=company) if company else Receiving.objects.all()
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    qs = qs.select_related('warehouse').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/receiving_list.html', {
        'receivings': page,
        'warehouses': warehouses,
        'selected_status': status,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def receiving_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = ReceivingForm(request.POST, company=company)
        if form.is_valid():
            rec = form.save(commit=False)
            rec.company = company
            rec.created_by = request.user
            if not rec.reference:
                rec.reference = _next_ref(company, 'WH', Receiving)
            rec.save()
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('expected_quantities')
            batch_numbers = request.POST.getlist('batch_numbers')
            for i, pid in enumerate(product_ids):
                if pid:
                    qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                    bn = batch_numbers[i] if i < len(batch_numbers) else ''
                    if qty > 0:
                        ReceivingItem.objects.create(
                            receiving=rec,
                            product_id=int(pid),
                            expected_quantity=qty,
                            batch_number=bn or '',
                        )
            messages.success(request, get_translation('receiving_created', lang))
            return redirect('warehouses:receiving_detail', pk=rec.pk)
    else:
        form = ReceivingForm(company=company)
    products = _get_products(company)
    return render(request, 'warehouses/receiving_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'lang': lang,
    })


@login_required
@never_cache
def receiving_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    receiving = get_object_or_404(Receiving, pk=pk, company=company)
    items = receiving.items.select_related('product', 'batch').all()
    return render(request, 'warehouses/receiving_detail.html', {
        'receiving': receiving,
        'items': items,
        'lang': lang,
    })


@login_required
@never_cache
def receiving_update_status(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    receiving = get_object_or_404(Receiving, pk=pk, company=company)
    new_status = request.POST.get('status')
    valid_statuses = dict(Receiving.STATUS_CHOICES)
    if new_status in valid_statuses and new_status != 'cancelled':
        receiving.status = new_status
        now = timezone.now()
        if new_status == 'arrived':
            receiving.actual_date = now.date()
        elif new_status == 'unloading':
            receiving.started_at = now
        elif new_status == 'completed':
            receiving.completed_at = now
            items = receiving.items.select_related('product', 'batch').all()
            for item in items:
                qty = item.received_quantity - item.damaged_quantity - item.rejected_quantity
                if qty > 0:
                    StockEngine.process_stock_change(
                        product=item.product,
                        warehouse=receiving.warehouse,
                        company=company,
                        direction='IN',
                        movement_type='purchase',
                        quantity=qty,
                        user=request.user,
                        reference_type='Receiving',
                        reference_id=receiving.pk,
                        reference_number=receiving.reference,
                        reason=f'Receiving {receiving.reference}',
                    )
                    locs = receiving.warehouse.locations.filter(
                        location_type='storage', is_active=True
                    ).first()
                    if locs:
                        sl_kwargs = dict(
                            company=company,
                            product=item.product,
                            warehouse=receiving.warehouse,
                            location=locs,
                        )
                        if item.batch:
                            sl_kwargs['batch'] = item.batch
                        sl, _ = StockLocation.objects.get_or_create(
                            **sl_kwargs,
                            defaults={'quantity': 0, 'reserved': 0},
                        )
                        sl.quantity += qty
                        sl.save(update_fields=['quantity', 'last_updated'])
        receiving.save()
        messages.success(request, get_translation('receiving_status_updated', lang))
    return redirect('warehouses:receiving_detail', pk=pk)


@login_required
@never_cache
def receiving_add_item(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    receiving = get_object_or_404(Receiving, pk=pk, company=company)
    if request.method == 'POST':
        product_id = request.POST.get('product')
        expected_qty = request.POST.get('expected_quantity', 0)
        batch_number = request.POST.get('batch_number', '')
        if product_id and expected_qty:
            ReceivingItem.objects.create(
                receiving=receiving,
                product_id=int(product_id),
                expected_quantity=int(expected_qty),
                batch_number=batch_number,
            )
            messages.success(request, get_translation('item_added', lang))
    return redirect('warehouses:receiving_detail', pk=pk)


@login_required
@never_cache
def putaway_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = PutAway.objects.filter(company=company) if company else PutAway.objects.all()
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    qs = qs.select_related('warehouse', 'receiving').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/putaway_list.html', {
        'putaways': page,
        'warehouses': warehouses,
        'selected_status': status,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def putaway_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    receiving_id = request.GET.get('receiving')
    initial = {}
    if receiving_id:
        initial['receiving'] = receiving_id
        try:
            rec = Receiving.objects.get(pk=receiving_id, company=company)
            initial['warehouse'] = rec.warehouse_id
        except Receiving.DoesNotExist:
            pass
    if request.method == 'POST':
        form = PutAwayForm(request.POST, company=company)
        if form.is_valid():
            pa = form.save(commit=False)
            pa.company = company
            if not pa.reference:
                pa.reference = _next_ref(company, 'PA', PutAway)
            pa.save()
            receiving = pa.receiving
            if receiving:
                for ri in receiving.items.select_related('product').all():
                    qty = ri.received_quantity - ri.damaged_quantity - ri.rejected_quantity
                    if qty > 0:
                        loc = pa.warehouse.locations.filter(
                            location_type='storage', is_active=True
                        ).first()
                        if loc:
                            PutAwayItem.objects.create(
                                putaway=pa,
                                product=ri.product,
                                quantity=qty,
                                batch=ri.batch,
                                to_location=loc,
                            )
            messages.success(request, get_translation('putaway_created', lang))
            return redirect('warehouses:putaway_detail', pk=pa.pk)
    else:
        form = PutAwayForm(company=company, initial=initial)
    return render(request, 'warehouses/putaway_form.html', {
        'form': form,
        'form_type': 'create',
        'lang': lang,
    })


@login_required
@never_cache
def putaway_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    putaway = get_object_or_404(PutAway, pk=pk, company=company)
    items = putaway.items.select_related('product', 'to_location', 'from_location').all()
    return render(request, 'warehouses/putaway_detail.html', {
        'putaway': putaway,
        'items': items,
        'lang': lang,
    })


@login_required
@never_cache
def putaway_confirm_item(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    putaway = get_object_or_404(PutAway, pk=pk, company=company)
    item_id = request.POST.get('item_id')
    if item_id and request.method == 'POST':
        item = get_object_or_404(PutAwayItem, pk=item_id, putaway=putaway)
        if not item.is_putaway:
            item.is_putaway = True
            item.save(update_fields=['is_putaway'])
            sl, _ = StockLocation.objects.get_or_create(
                company=company,
                product=item.product,
                warehouse=putaway.warehouse,
                location=item.to_location,
                batch=item.batch,
                defaults={'quantity': 0, 'reserved': 0},
            )
            sl.quantity += item.quantity
            sl.save(update_fields=['quantity', 'last_updated'])
            messages.success(request, get_translation('item_putaway_confirmed', lang))
        else:
            messages.info(request, get_translation('item_already_putaway', lang))
        if putaway.completed_items == putaway.total_items:
            putaway.status = 'completed'
            putaway.completed_at = timezone.now()
            putaway.save(update_fields=['status', 'completed_at'])
    return redirect('warehouses:putaway_detail', pk=pk)


@login_required
@never_cache
def picking_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = PickingList.objects.filter(company=company) if company else PickingList.objects.all()
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    qs = qs.select_related('warehouse').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/picking_list.html', {
        'pickings': page,
        'warehouses': warehouses,
        'selected_status': status,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def picking_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = PickingListForm(request.POST, company=company)
        if form.is_valid():
            pl = form.save(commit=False)
            pl.company = company
            if not pl.reference:
                pl.reference = _next_ref(company, 'PL', PickingList)
            pl.save()
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            location_ids = request.POST.getlist('locations')
            for i, pid in enumerate(product_ids):
                if pid:
                    qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                    loc_id = location_ids[i] if i < len(location_ids) and location_ids[i] else None
                    if qty > 0:
                        PickingItem.objects.create(
                            picking_list=pl,
                            product_id=int(pid),
                            quantity=qty,
                            location_id=int(loc_id) if loc_id else None,
                        )
            messages.success(request, get_translation('picking_created', lang))
            return redirect('warehouses:picking_detail', pk=pl.pk)
    else:
        form = PickingListForm(company=company)
    products = _get_products(company)
    locations = _get_locations(company)
    return render(request, 'warehouses/picking_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'locations': locations,
        'lang': lang,
    })


@login_required
@never_cache
def picking_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    picking = get_object_or_404(PickingList, pk=pk, company=company)
    items = picking.items.select_related('product', 'location', 'batch').all()
    return render(request, 'warehouses/picking_detail.html', {
        'picking': picking,
        'items': items,
        'lang': lang,
    })


@login_required
@never_cache
def picking_start(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    picking = get_object_or_404(PickingList, pk=pk, company=company)
    if request.method == 'POST' and picking.status in ('pending', 'assigned', 'draft'):
        picking.status = 'in_progress'
        picking.started_at = timezone.now()
        picking.save(update_fields=['status', 'started_at'])
        messages.success(request, get_translation('picking_started', lang))
    return redirect('warehouses:picking_detail', pk=pk)


@login_required
@never_cache
def picking_confirm_item(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    picking = get_object_or_404(PickingList, pk=pk, company=company)
    item_id = request.POST.get('item_id')
    if item_id and request.method == 'POST':
        item = get_object_or_404(PickingItem, pk=item_id, picking_list=picking)
        picked_qty = request.POST.get('picked_quantity')
        is_short = request.POST.get('is_short_pick')
        if picked_qty:
            item.picked_quantity = int(picked_qty)
        if is_short:
            item.is_short_pick = True
        item.is_picked = True
        item.save(update_fields=['picked_quantity', 'is_picked', 'is_short_pick'])
        messages.success(request, get_translation('item_picked', lang))
    return redirect('warehouses:picking_detail', pk=pk)


@login_required
@never_cache
def picking_complete(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    picking = get_object_or_404(PickingList, pk=pk, company=company)
    if request.method == 'POST':
        picking.status = 'completed'
        picking.completed_at = timezone.now()
        picking.save(update_fields=['status', 'completed_at'])
        messages.success(request, get_translation('picking_completed', lang))
    return redirect('warehouses:picking_detail', pk=pk)


@login_required
@never_cache
def packing_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = PackingList.objects.filter(company=company) if company else PackingList.objects.all()
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    qs = qs.select_related('warehouse').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/packing_list.html', {
        'packings': page,
        'warehouses': warehouses,
        'selected_status': status,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def packing_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = PackingListForm(request.POST, company=company)
        if form.is_valid():
            pk_obj = form.save(commit=False)
            pk_obj.company = company
            if not pk_obj.reference:
                pk_obj.reference = _next_ref(company, 'PK', PackingList)
            pk_obj.save()
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            for i, pid in enumerate(product_ids):
                if pid:
                    qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                    if qty > 0:
                        PackingItem.objects.create(
                            packing_list=pk_obj,
                            product_id=int(pid),
                            quantity=qty,
                        )
            messages.success(request, get_translation('packing_created', lang))
            return redirect('warehouses:packing_detail', pk=pk_obj.pk)
    else:
        form = PackingListForm(company=company)
    products = _get_products(company)
    return render(request, 'warehouses/packing_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'lang': lang,
    })


@login_required
@never_cache
def packing_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    packing = get_object_or_404(PackingList, pk=pk, company=company)
    items = packing.items.select_related('product').all()
    return render(request, 'warehouses/packing_detail.html', {
        'packing': packing,
        'items': items,
        'lang': lang,
    })


@login_required
@never_cache
def packing_confirm_item(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    packing = get_object_or_404(PackingList, pk=pk, company=company)
    item_id = request.POST.get('item_id')
    if item_id and request.method == 'POST':
        item = get_object_or_404(PackingItem, pk=item_id, packing_list=packing)
        packed_qty = request.POST.get('packed_quantity')
        package_number = request.POST.get('package_number', '')
        weight = request.POST.get('weight')
        if packed_qty:
            item.packed_quantity = int(packed_qty)
        if package_number:
            item.package_number = package_number
        if weight:
            item.weight = weight
        item.is_packed = True
        item.save(update_fields=['packed_quantity', 'package_number', 'weight', 'is_packed'])
        messages.success(request, get_translation('item_packed', lang))
    return redirect('warehouses:packing_detail', pk=pk)


@login_required
@never_cache
def packing_complete(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    packing = get_object_or_404(PackingList, pk=pk, company=company)
    if request.method == 'POST':
        packing.status = 'packed'
        packing.completed_at = timezone.now()
        packing.package_count = packing.items.filter(is_packed=True).count()
        packing.save(update_fields=['status', 'completed_at', 'package_count'])
        messages.success(request, get_translation('packing_completed', lang))
    return redirect('warehouses:packing_detail', pk=pk)


@login_required
@never_cache
def shipment_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = Shipment.objects.filter(company=company) if company else Shipment.objects.all()
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    qs = qs.select_related('warehouse').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/shipment_list.html', {
        'shipments': page,
        'warehouses': warehouses,
        'selected_status': status,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def shipment_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = ShipmentForm(request.POST, company=company)
        if form.is_valid():
            ship = form.save(commit=False)
            ship.company = company
            ship.created_by = request.user
            if not ship.reference:
                ship.reference = _next_ref(company, 'SH', Shipment)
            ship.save()
            pkg_count = request.POST.get('package_count', 0)
            for i in range(1, int(pkg_count) + 1):
                ShipmentPackage.objects.create(
                    shipment=ship,
                    package_number=f"PKG-{i:03d}",
                    weight=request.POST.get(f'pkg_weight_{i}') or None,
                    length=request.POST.get(f'pkg_length_{i}') or None,
                    width=request.POST.get(f'pkg_width_{i}') or None,
                    height=request.POST.get(f'pkg_height_{i}') or None,
                )
            messages.success(request, get_translation('shipment_created', lang))
            return redirect('warehouses:shipment_detail', pk=ship.pk)
    else:
        form = ShipmentForm(company=company)
    return render(request, 'warehouses/shipment_form.html', {
        'form': form,
        'form_type': 'create',
        'lang': lang,
    })


@login_required
@never_cache
def shipment_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    shipment = get_object_or_404(Shipment, pk=pk, company=company)
    packages = shipment.packages.all()
    return render(request, 'warehouses/shipment_detail.html', {
        'shipment': shipment,
        'packages': packages,
        'lang': lang,
    })


@login_required
@never_cache
def shipment_update_status(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    shipment = get_object_or_404(Shipment, pk=pk, company=company)
    new_status = request.POST.get('status')
    valid_statuses = dict(Shipment.STATUS_CHOICES)
    if new_status in valid_statuses:
        shipment.status = new_status
        now = timezone.now()
        if new_status == 'shipped':
            shipment.shipped_date = now.date()
        elif new_status == 'delivered':
            shipment.delivered_date = now.date()
        carrier = request.POST.get('carrier')
        if carrier:
            shipment.carrier = carrier
        tracking = request.POST.get('tracking_number')
        if tracking:
            shipment.tracking_number = tracking
        shipment.save()
        messages.success(request, get_translation('shipment_status_updated', lang))
    return redirect('warehouses:shipment_detail', pk=pk)


@login_required
@never_cache
def transfer_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = Transfer.objects.filter(company=company) if company else Transfer.objects.all()
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(Q(from_warehouse_id=warehouse_id) | Q(to_warehouse_id=warehouse_id))
    qs = qs.select_related('from_warehouse', 'to_warehouse').order_by('-created_at')
    total_count = qs.count()
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/transfer_list.html', {
        'page_obj': page,
        'total_count': total_count,
        'warehouses': warehouses,
        'selected_status': status,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def transfer_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = TransferForm(request.POST, company=company)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.company = company
            transfer.created_by = request.user
            if not transfer.reference:
                transfer.reference = _next_ref(company, 'TS', Transfer)
            transfer.save()
            product_ids = request.POST.getlist('products')
            quantities = request.POST.getlist('quantities')
            for i, pid in enumerate(product_ids):
                if pid:
                    qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                    if qty > 0:
                        TransferItem.objects.create(
                            transfer=transfer,
                            product_id=int(pid),
                            quantity=qty,
                        )
            messages.success(request, get_translation('transfer_created', lang))
            return redirect('warehouses:transfer_detail', pk=transfer.pk)
    else:
        form = TransferForm(company=company)
    products = _get_products(company)
    warehouses = _get_warehouses(company)
    locations = _get_locations(company)
    return render(request, 'warehouses/transfer_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'warehouses': warehouses,
        'locations': locations,
        'lang': lang,
    })


@login_required
@never_cache
def transfer_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    transfer = get_object_or_404(Transfer, pk=pk, company=company)
    items = transfer.items.select_related('product', 'batch', 'from_location', 'to_location').all()
    return render(request, 'warehouses/transfer_detail.html', {
        'transfer': transfer,
        'items': items,
        'lang': lang,
    })


@login_required
@never_cache
def transfer_update_status(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    transfer = get_object_or_404(Transfer, pk=pk, company=company)
    new_status = request.POST.get('status')
    valid_statuses = dict(Transfer.STATUS_CHOICES)
    if new_status in valid_statuses:
        now = timezone.now()
        transfer.status = new_status
        if new_status == 'approved':
            transfer.approved_by = request.user
        elif new_status == 'shipped':
            transfer.shipped_by = request.user
            transfer.shipped_at = now
            for item in transfer.items.select_related('product').all():
                qty = item.quantity - item.shipped_quantity
                if qty > 0:
                    StockEngine.process_stock_change(
                        product=item.product,
                        warehouse=transfer.from_warehouse,
                        company=company,
                        direction='OUT',
                        movement_type='transfer_out',
                        quantity=qty,
                        user=request.user,
                        reference_type='Transfer',
                        reference_id=transfer.pk,
                        reference_number=transfer.reference,
                        reason=f'Transfer out {transfer.reference}',
                    )
                    item.shipped_quantity = item.quantity
                    item.save(update_fields=['shipped_quantity'])
        elif new_status == 'received':
            transfer.received_by = request.user
            transfer.received_at = now
            for item in transfer.items.select_related('product').all():
                qty = item.quantity - item.received_quantity
                if qty > 0:
                    StockEngine.process_stock_change(
                        product=item.product,
                        warehouse=transfer.to_warehouse,
                        company=company,
                        direction='IN',
                        movement_type='transfer_in',
                        quantity=qty,
                        user=request.user,
                        reference_type='Transfer',
                        reference_id=transfer.pk,
                        reference_number=transfer.reference,
                        reason=f'Transfer in {transfer.reference}',
                    )
                    item.received_quantity = item.quantity
                    item.save(update_fields=['received_quantity'])
        transfer.save()
        messages.success(request, get_translation('transfer_status_updated', lang))
    return redirect('warehouses:transfer_detail', pk=pk)


@login_required
@never_cache
def transfer_add_item(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    transfer = get_object_or_404(Transfer, pk=pk, company=company)
    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity', 0)
        if product_id and quantity:
            TransferItem.objects.create(
                transfer=transfer,
                product_id=int(product_id),
                quantity=int(quantity),
            )
            messages.success(request, get_translation('item_added', lang))
    return redirect('warehouses:transfer_detail', pk=pk)


@login_required
@never_cache
def batch_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = Batch.objects.filter(company=company) if company else Batch.objects.all()
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get('product')
    if product_id:
        qs = qs.filter(product_id=product_id)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(batch_number__icontains=q)
    qs = qs.select_related('product', 'warehouse', 'location').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    products = _get_products(company)
    return render(request, 'warehouses/batch_list.html', {
        'page_obj': page,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
        'q': q,
        'lang': lang,
    })


@login_required
@never_cache
def batch_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = BatchForm(request.POST, company=company)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.company = company
            batch.save()
            messages.success(request, get_translation('batch_created', lang))
            return redirect('warehouses:batch_detail', pk=batch.pk)
    else:
        form = BatchForm(company=company)
    products = _get_products(company)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/batch_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'warehouses': warehouses,
        'lang': lang,
    })


@login_required
@never_cache
def batch_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    batch = get_object_or_404(Batch, pk=pk, company=company)
    serials = batch.serial_numbers.select_related('product').all()
    return render(request, 'warehouses/batch_detail.html', {
        'batch': batch,
        'serials': serials,
        'lang': lang,
    })


@login_required
@never_cache
def serial_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = SerialNumber.objects.filter(company=company) if company else SerialNumber.objects.all()
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get('product')
    if product_id:
        qs = qs.filter(product_id=product_id)
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(serial__icontains=q)
    qs = qs.select_related('product', 'warehouse', 'location').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    products = _get_products(company)
    return render(request, 'warehouses/serial_list.html', {
        'page_obj': page,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
        'selected_status': status,
        'q': q,
        'lang': lang,
    })


@login_required
@never_cache
def serial_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = SerialNumberForm(request.POST, company=company)
        if form.is_valid():
            sn = form.save(commit=False)
            sn.company = company
            sn.save()
            messages.success(request, get_translation('serial_created', lang))
            return redirect('warehouses:serial_detail', pk=sn.pk)
    else:
        form = SerialNumberForm(company=company)
    products = _get_products(company)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/serial_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'warehouses': warehouses,
        'lang': lang,
    })


@login_required
@never_cache
def serial_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    serial = get_object_or_404(SerialNumber, pk=pk, company=company)
    return render(request, 'warehouses/serial_detail.html', {
        'serial': serial,
        'lang': lang,
    })


@login_required
@never_cache
def task_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = WarehouseTask.objects.filter(company=company) if company else WarehouseTask.objects.all()
    task_type = request.GET.get('type')
    if task_type:
        qs = qs.filter(task_type=task_type)
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    assigned_to = request.GET.get('assigned_to')
    if assigned_to:
        qs = qs.filter(assigned_to_id=assigned_to)
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    qs = qs.select_related('warehouse', 'assigned_to').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    users = _get_users(company)
    return render(request, 'warehouses/task_list.html', {
        'tasks': page,
        'warehouses': warehouses,
        'users': users,
        'selected_type': task_type,
        'selected_status': status,
        'selected_assigned_to': assigned_to,
        'selected_warehouse': warehouse_id,
        'lang': lang,
    })


@login_required
@never_cache
def task_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = WarehouseTaskForm(request.POST, company=company)
        if form.is_valid():
            task = form.save(commit=False)
            task.company = company
            task.created_by = request.user
            if not task.reference:
                task.reference = _next_ref(company, 'TK', WarehouseTask)
            task.save()
            messages.success(request, get_translation('task_created', lang))
            return redirect('warehouses:task_detail', pk=task.pk)
    else:
        form = WarehouseTaskForm(company=company)
    warehouses = _get_warehouses(company)
    users = _get_users(company)
    return render(request, 'warehouses/task_form.html', {
        'form': form,
        'form_type': 'create',
        'warehouses': warehouses,
        'users': users,
        'lang': lang,
    })


@login_required
@never_cache
def task_detail(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    task = get_object_or_404(WarehouseTask, pk=pk, company=company)
    return render(request, 'warehouses/task_detail.html', {
        'task': task,
        'lang': lang,
    })


@login_required
@never_cache
def task_update(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    task = get_object_or_404(WarehouseTask, pk=pk, company=company)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        assigned_to_id = request.POST.get('assigned_to')
        valid_statuses = dict(WarehouseTask.STATUS_CHOICES)
        now = timezone.now()
        if new_status and new_status in valid_statuses:
            task.status = new_status
            if new_status == 'in_progress' and not task.started_at:
                task.started_at = now
            elif new_status == 'completed' and not task.completed_at:
                task.completed_at = now
        if assigned_to_id:
            task.assigned_to_id = int(assigned_to_id)
        elif assigned_to_id == '':
            task.assigned_to = None
        task.save()
        messages.success(request, get_translation('task_updated', lang))
    return redirect('warehouses:task_detail', pk=pk)


@login_required
@never_cache
def damaged_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = DamagedStock.objects.filter(company=company) if company else DamagedStock.objects.all()
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get('product')
    if product_id:
        qs = qs.filter(product_id=product_id)
    qs = qs.select_related('product', 'warehouse', 'location', 'reported_by').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    products = _get_products(company)
    return render(request, 'warehouses/damaged_list.html', {
        'damaged_items': page,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
        'lang': lang,
    })


@login_required
@never_cache
def damaged_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = DamagedStockForm(request.POST, company=company)
        if form.is_valid():
            ds = form.save(commit=False)
            ds.company = company
            ds.reported_by = request.user
            ds.save()
            StockEngine.process_stock_change(
                product=ds.product,
                warehouse=ds.warehouse,
                company=company,
                direction='OUT',
                movement_type='damage',
                quantity=ds.quantity,
                user=request.user,
                reference_type='DamagedStock',
                reference_id=ds.pk,
                reference_number=f'DMG-{ds.pk:04d}',
                reason=ds.reason or 'Damaged stock',
            )
            messages.success(request, get_translation('damaged_created', lang))
            return redirect('warehouses:damaged_list')
    else:
        form = DamagedStockForm(company=company)
    products = _get_products(company)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/damaged_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'warehouses': warehouses,
        'lang': lang,
    })


@login_required
@never_cache
def quarantine_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = QuarantineStock.objects.filter(company=company) if company else QuarantineStock.objects.all()
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get('product')
    if product_id:
        qs = qs.filter(product_id=product_id)
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    qs = qs.select_related('product', 'warehouse', 'location', 'reported_by').order_by('-created_at')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    products = _get_products(company)
    return render(request, 'warehouses/quarantine_list.html', {
        'quarantine_items': page,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
        'selected_status': status,
        'lang': lang,
    })


@login_required
@never_cache
def quarantine_create(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        form = QuarantineStockForm(request.POST, company=company)
        if form.is_valid():
            qs = form.save(commit=False)
            qs.company = company
            qs.reported_by = request.user
            qs.save()
            StockEngine.process_stock_change(
                product=qs.product,
                warehouse=qs.warehouse,
                company=company,
                direction='OUT',
                movement_type='adjustment_decrease',
                quantity=qs.quantity,
                user=request.user,
                reference_type='QuarantineStock',
                reference_id=qs.pk,
                reference_number=f'QT-{qs.pk:04d}',
                reason=qs.reason or 'Quarantine stock',
            )
            messages.success(request, get_translation('quarantine_created', lang))
            return redirect('warehouses:quarantine_list')
    else:
        form = QuarantineStockForm(company=company)
    products = _get_products(company)
    warehouses = _get_warehouses(company)
    return render(request, 'warehouses/quarantine_form.html', {
        'form': form,
        'form_type': 'create',
        'products': products,
        'warehouses': warehouses,
        'lang': lang,
    })


@login_required
@never_cache
def wms_dashboard(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    today = timezone.now().date()
    warehouses = Warehouse.objects.filter(company=company, is_active=True)
    receiving_today = Receiving.objects.filter(
        company=company, expected_date=today
    ).exclude(status__in=('completed', 'cancelled')).count()
    pending_putaway = PutAway.objects.filter(
        company=company, status__in=('pending', 'in_progress')
    ).count()
    pending_picking = PickingList.objects.filter(
        company=company, status__in=('draft', 'pending', 'assigned')
    ).count()
    pending_packing = PackingList.objects.filter(
        company=company, status__in=('pending', 'in_progress')
    ).count()
    ready_to_ship = Shipment.objects.filter(
        company=company, status__in=('ready', 'packed')
    ).count()
    pending_transfers = Transfer.objects.filter(
        company=company, status__in=('draft', 'pending', 'approved')
    ).count()
    total_warehouses = warehouses.count()
    total_locations = Location.objects.filter(company=company, is_active=True).count()
    total_products = Product.objects.filter(company=company).count() if company else Product.objects.all().count()
    low_stock_products = Product.objects.filter(
        company=company, quantity__gt=0, quantity__lte=F('min_stock')
    ).count()
    near_expiry = Batch.objects.filter(
        company=company,
        expiry_date__isnull=False,
        expiry_date__lte=today + timedelta(days=30),
        expiry_date__gte=today,
        status='active',
    ).count()
    damaged_count = DamagedStock.objects.filter(
        company=company, created_at__date=today
    ).count()
    quarantine_count = QuarantineStock.objects.filter(
        company=company, status='quarantined'
    ).count()
    recent_receiving = Receiving.objects.filter(
        company=company
    ).select_related('warehouse').order_by('-created_at')[:5]
    recent_pickings = PickingList.objects.filter(
        company=company
    ).select_related('warehouse').order_by('-created_at')[:5]
    recent_shipments = Shipment.objects.filter(
        company=company
    ).select_related('warehouse').order_by('-created_at')[:5]
    return render(request, 'warehouses/wms_dashboard.html', {
        'warehouses': warehouses,
        'receiving_today': receiving_today,
        'pending_putaway': pending_putaway,
        'pending_picking': pending_picking,
        'pending_packing': pending_packing,
        'ready_to_ship': ready_to_ship,
        'pending_transfers': pending_transfers,
        'total_warehouses': total_warehouses,
        'total_locations': total_locations,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'near_expiry': near_expiry,
        'damaged_count': damaged_count,
        'quarantine_count': quarantine_count,
        'recent_receiving': recent_receiving,
        'recent_pickings': recent_pickings,
        'recent_shipments': recent_shipments,
        'lang': lang,
    })


@login_required
@never_cache
def warehouse_dashboard(request, pk):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    warehouse = get_object_or_404(Warehouse, pk=pk, company=company)
    stock_levels = StockLevel.objects.filter(
        company=company, warehouse=warehouse
    ).select_related('product').order_by('-quantity')
    total_stock = stock_levels.aggregate(s=Sum('quantity'))['s'] or 0
    total_reserved = stock_levels.aggregate(s=Sum('reserved'))['s'] or 0
    zones = warehouse.zones.filter(is_active=True)
    locations = warehouse.locations.filter(is_active=True)
    location_count = locations.count()
    active_receiving = Receiving.objects.filter(
        company=company, warehouse=warehouse
    ).exclude(status__in=('completed', 'cancelled')).count()
    active_picking = PickingList.objects.filter(
        company=company, warehouse=warehouse
    ).exclude(status__in=('completed', 'cancelled')).count()
    active_packing = PackingList.objects.filter(
        company=company, warehouse=warehouse
    ).exclude(status__in=('packed', 'cancelled')).count()
    pending_tasks = WarehouseTask.objects.filter(
        company=company, warehouse=warehouse,
        status__in=('pending', 'assigned', 'in_progress')
    ).count()
    low_stock = Product.objects.filter(
        company=company, quantity__gt=0, quantity__lte=F('min_stock')
    ).count()
    damaged = DamagedStock.objects.filter(
        company=company, warehouse=warehouse
    ).count()
    quarantine = QuarantineStock.objects.filter(
        company=company, warehouse=warehouse, status='quarantined'
    ).count()
    recent_movements = StockMovement.objects.filter(
        company=company, warehouse=warehouse
    ).select_related('product').order_by('-created_at')[:10]
    return render(request, 'warehouses/warehouse_dashboard.html', {
        'warehouse': warehouse,
        'stock_levels': stock_levels[:50],
        'total_stock': total_stock,
        'total_reserved': total_reserved,
        'zones': zones,
        'locations': locations[:20],
        'location_count': location_count,
        'active_receiving': active_receiving,
        'active_picking': active_picking,
        'active_packing': active_packing,
        'pending_tasks': pending_tasks,
        'low_stock': low_stock,
        'damaged': damaged,
        'quarantine': quarantine,
        'recent_movements': recent_movements,
        'lang': lang,
    })


@login_required
@never_cache
def stock_location_list(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    qs = StockLocation.objects.filter(company=company) if company else StockLocation.objects.all()
    warehouse_id = request.GET.get('warehouse')
    if warehouse_id:
        qs = qs.filter(warehouse_id=warehouse_id)
    product_id = request.GET.get('product')
    if product_id:
        qs = qs.filter(product_id=product_id)
    qs = qs.select_related('product', 'warehouse', 'location', 'batch').order_by('location__code', '-quantity')
    page = _paginate(request, qs)
    warehouses = _get_warehouses(company)
    products = _get_products(company)
    return render(request, 'warehouses/stock_location_list.html', {
        'stock_locations': page,
        'warehouses': warehouses,
        'products': products,
        'selected_warehouse': warehouse_id,
        'selected_product': product_id,
        'lang': lang,
    })


@login_required
@never_cache
def stock_location_move(request):
    company = _get_company(request)
    if company is None and not request.user.is_superuser:
        return redirect('login')
    lang = _lang(request)
    if request.method == 'POST':
        stock_location_id = request.POST.get('stock_location_id')
        to_location_id = request.POST.get('to_location_id')
        quantity = request.POST.get('quantity')
        if stock_location_id and to_location_id and quantity:
            sl = get_object_or_404(StockLocation, pk=stock_location_id, company=company)
            to_location = get_object_or_404(Location, pk=to_location_id, company=company)
            qty = int(quantity)
            if qty > 0 and qty <= sl.available:
                sl.quantity -= qty
                sl.save(update_fields=['quantity', 'last_updated'])
                dest_sl, _ = StockLocation.objects.get_or_create(
                    company=company,
                    product=sl.product,
                    warehouse=sl.warehouse,
                    location=to_location,
                    batch=sl.batch,
                    defaults={'quantity': 0, 'reserved': 0},
                )
                dest_sl.quantity += qty
                dest_sl.save(update_fields=['quantity', 'last_updated'])
                StockMovement.objects.create(
                    company=company,
                    product=sl.product,
                    warehouse=sl.warehouse,
                    direction='OUT',
                    movement_type='stock_out',
                    quantity=qty,
                    before_quantity=sl.quantity + qty,
                    after_quantity=sl.quantity,
                    reference_type='StockLocation',
                    reference_id=sl.pk,
                    reference_number=f'MOVE-{sl.pk}',
                    user=request.user,
                    reason=f'Moved from {sl.location} to {to_location}',
                )
                StockMovement.objects.create(
                    company=company,
                    product=sl.product,
                    warehouse=sl.warehouse,
                    direction='IN',
                    movement_type='stock_in',
                    quantity=qty,
                    before_quantity=dest_sl.quantity - qty,
                    after_quantity=dest_sl.quantity,
                    reference_type='StockLocation',
                    reference_id=dest_sl.pk,
                    reference_number=f'MOVE-{dest_sl.pk}',
                    user=request.user,
                    reason=f'Moved from {sl.location} to {to_location}',
                )
                messages.success(request, get_translation('stock_moved', lang))
            else:
                messages.error(request, get_translation('invalid_quantity', lang))
    warehouse_id = request.GET.get('warehouse') or request.POST.get('warehouse')
    if warehouse_id:
        return redirect(f"{request.path}?warehouse={warehouse_id}")
    return redirect('warehouses:warehouse_list')
