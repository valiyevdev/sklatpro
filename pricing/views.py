import json
from decimal import Decimal, InvalidOperation
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.core.paginator import Paginator

from core.translations import get_translation
from users.models import Company
from products.models import Product, ProductVariant, Category
from sales.models import Customer
from .models import (
    PriceList, PriceListEntry, CustomerSpecificPrice,
    Promotion, Coupon, CouponUsage, PriceHistory,
)
from .engine import resolve_price, resolve_line_price


def _lang(request):
    return request.session.get('language', 'uz')


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if company:
        return company
    if request.user.is_superuser:
        from users.models import Company as C
        return C.objects.first()
    return None


def _t(key, lang=None):
    return get_translation(key, lang or 'uz')


@login_required
@never_cache
def pricing_dashboard(request):
    company = _get_company(request)
    lang = _lang(request)
    today = date.today()

    price_lists = PriceList.objects.filter(company=company) if company else PriceList.objects.all()
    active_plists = price_lists.filter(status='active')
    promotions = Promotion.objects.filter(company=company) if company else Promotion.objects.all()
    active_promos = promotions.filter(status='active', start_date__lte=today, end_date__gte=today)
    coupons = Coupon.objects.filter(company=company) if company else Coupon.objects.all()
    active_coupons = coupons.filter(is_active=True)
    customer_prices = CustomerSpecificPrice.objects.filter(company=company, is_active=True) if company else CustomerSpecificPrice.objects.filter(is_active=True)

    recent_history = PriceHistory.objects.filter(
        company=company
    ).select_related('product', 'price_list', 'changed_by')[:10] if company else PriceHistory.objects.select_related('product', 'changed_by')[:10]

    ctx = {
        'total_plists': price_lists.count(),
        'active_plists': active_plists.count(),
        'total_entries': PriceListEntry.objects.filter(price_list__company=company).count() if company else 0,
        'total_promos': promotions.count(),
        'active_promos': active_promos.count(),
        'total_coupons': coupons.count(),
        'active_coupons': active_coupons.count(),
        'total_customer_prices': customer_prices.count(),
        'recent_history': recent_history,
        'active_plists_list': active_plists[:5],
        'active_promos_list': active_promos[:5],
    }
    return render(request, 'pricing/dashboard.html', ctx)


@login_required
@never_cache
def price_list_list(request):
    company = _get_company(request)
    lang = _lang(request)
    q = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    pls = PriceList.objects.filter(company=company) if company else PriceList.objects.all()
    if q:
        pls = pls.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if status_filter:
        pls = pls.filter(status=status_filter)
    pls = pls.annotate(entry_count_real=Count('entries'))
    pls = pls.order_by('-priority', 'name')

    paginator = Paginator(pls, 20)
    page = paginator.get_page(request.GET.get('page'))

    ctx = {'page': page, 'search': q, 'status_filter': status_filter}
    return render(request, 'pricing/price_list_list.html', ctx)


@login_required
@never_cache
def price_list_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        if name and code:
            pl = PriceList(
                company=company,
                name=name,
                code=code,
                description=request.POST.get('description', ''),
                currency=request.POST.get('currency', 'UZS'),
                status=request.POST.get('status', 'active'),
                priority=int(request.POST.get('priority', 0)),
                channel=request.POST.get('channel', ''),
                is_default=request.POST.get('is_default') == 'on',
            )
            sd = request.POST.get('start_date')
            ed = request.POST.get('end_date')
            if sd:
                pl.start_date = sd
            if ed:
                pl.end_date = ed
            seg_id = request.POST.get('customer_segment')
            if seg_id:
                from crm.models import CustomerSegment
                try:
                    pl.customer_segment = CustomerSegment.objects.get(pk=seg_id, company=company)
                except CustomerSegment.DoesNotExist:
                    pass
            wh_id = request.POST.get('warehouse')
            if wh_id:
                from warehouses.models import Warehouse
                try:
                    pl.warehouse = Warehouse.objects.get(pk=wh_id)
                except Warehouse.DoesNotExist:
                    pass
            pl.save()
            messages.success(request, _t('price_list_created', lang))
            return redirect('pricing:price_list_detail', pk=pl.pk)
        messages.error(request, _t('fill_required_fields', lang))

    from crm.models import CustomerSegment
    from warehouses.models import Warehouse
    ctx = {
        'segments': CustomerSegment.objects.filter(company=company) if company else [],
        'warehouses': Warehouse.objects.all(),
    }
    return render(request, 'pricing/price_list_form.html', ctx)


@login_required
@never_cache
def price_list_detail(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    pl = get_object_or_404(PriceList, pk=pk)
    if company and pl.company != company:
        return redirect('pricing:pricing_dashboard')

    entries = pl.entries.select_related('product', 'variant').order_by('product__name')

    ctx = {'pl': pl, 'entries': entries}
    return render(request, 'pricing/price_list_detail.html', ctx)


@login_required
@never_cache
def price_list_edit(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    pl = get_object_or_404(PriceList, pk=pk)
    if company and pl.company != company:
        return redirect('pricing:pricing_dashboard')

    if request.method == 'POST':
        pl.name = request.POST.get('name', pl.name)
        pl.code = request.POST.get('code', pl.code)
        pl.description = request.POST.get('description', '')
        pl.currency = request.POST.get('currency', pl.currency)
        pl.status = request.POST.get('status', pl.status)
        pl.priority = int(request.POST.get('priority', pl.priority))
        pl.channel = request.POST.get('channel', pl.channel)
        pl.is_default = request.POST.get('is_default') == 'on'
        sd = request.POST.get('start_date')
        ed = request.POST.get('end_date')
        pl.start_date = sd if sd else None
        pl.end_date = ed if ed else None
        seg_id = request.POST.get('customer_segment')
        if seg_id:
            from crm.models import CustomerSegment
            try:
                pl.customer_segment = CustomerSegment.objects.get(pk=seg_id, company=company)
            except CustomerSegment.DoesNotExist:
                pl.customer_segment = None
        else:
            pl.customer_segment = None
        wh_id = request.POST.get('warehouse')
        if wh_id:
            from warehouses.models import Warehouse
            try:
                pl.warehouse = Warehouse.objects.get(pk=wh_id)
            except Warehouse.DoesNotExist:
                pl.warehouse = None
        else:
            pl.warehouse = None
        pl.save()
        messages.success(request, _t('price_list_updated', lang))
        return redirect('pricing:price_list_detail', pk=pl.pk)

    from crm.models import CustomerSegment
    from warehouses.models import Warehouse
    ctx = {
        'pl': pl,
        'segments': CustomerSegment.objects.filter(company=company) if company else [],
        'warehouses': Warehouse.objects.all(),
    }
    return render(request, 'pricing/price_list_form.html', ctx)


@login_required
@require_POST
@never_cache
def price_list_delete(request, pk):
    company = _get_company(request)
    pl = get_object_or_404(PriceList, pk=pk)
    if company and pl.company != company:
        return redirect('pricing:pricing_dashboard')
    pl.delete()
    messages.success(request, _t('price_list_deleted', _lang(request)))
    return redirect('pricing:price_list_list')


@login_required
@never_cache
def entry_add(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    pl = get_object_or_404(PriceList, pk=pk)
    if company and pl.company != company:
        return redirect('pricing:pricing_dashboard')

    if request.method == 'POST':
        product_id = request.POST.get('product')
        price = request.POST.get('price')
        if product_id and price:
            product = Product.objects.get(pk=product_id)
            old_price = None
            try:
                old_price = product.price
            except Exception:
                pass
            variant_id = request.POST.get('variant')
            variant = None
            if variant_id:
                variant = ProductVariant.objects.get(pk=variant_id)

            entry = PriceListEntry(
                price_list=pl,
                product=product,
                variant=variant,
                price=Decimal(price),
                min_quantity=int(request.POST.get('min_quantity', 1)),
                max_quantity=int(request.POST['max_quantity']) if request.POST.get('max_quantity') else None,
                is_active=request.POST.get('is_active', 'on') == 'on',
            )
            sd = request.POST.get('start_date')
            ed = request.POST.get('end_date')
            if sd:
                entry.start_date = sd
            if ed:
                entry.end_date = ed
            entry.save()

            PriceHistory.objects.create(
                company=company or pl.company,
                product=product,
                variant=variant,
                price_list=pl,
                old_price=old_price or Decimal('0'),
                new_price=entry.price,
                change_type='price_list',
                reason=f'Added to price list {pl.code}',
                changed_by=request.user,
            )
            messages.success(request, _t('entry_added', lang))
            return redirect('pricing:price_list_detail', pk=pl.pk)

    products = Product.objects.all()
    ctx = {'pl': pl, 'products': products}
    return render(request, 'pricing/entry_form.html', ctx)


@login_required
@never_cache
def entry_edit(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    entry = get_object_or_404(PriceListEntry, pk=pk)
    if company and entry.price_list.company != company:
        return redirect('pricing:pricing_dashboard')

    if request.method == 'POST':
        price = request.POST.get('price')
        if price:
            old_price = entry.price
            entry.price = Decimal(price)
            entry.min_quantity = int(request.POST.get('min_quantity', entry.min_quantity))
            mq = request.POST.get('max_quantity')
            entry.max_quantity = int(mq) if mq else None
            entry.is_active = request.POST.get('is_active', 'on') == 'on'
            sd = request.POST.get('start_date')
            ed = request.POST.get('end_date')
            entry.start_date = sd if sd else None
            entry.end_date = ed if ed else None
            entry.save()

            PriceHistory.objects.create(
                company=company or entry.price_list.company,
                product=entry.product,
                variant=entry.variant,
                price_list=entry.price_list,
                old_price=old_price,
                new_price=entry.price,
                change_type='price_list',
                reason=f'Updated in price list {entry.price_list.code}',
                changed_by=request.user,
            )
            messages.success(request, _t('entry_updated', lang))
        return redirect('pricing:price_list_detail', pk=entry.price_list.pk)

    ctx = {'entry': entry, 'pl': entry.price_list}
    return render(request, 'pricing/entry_form.html', ctx)


@login_required
@require_POST
@never_cache
def entry_delete(request, pk):
    company = _get_company(request)
    entry = get_object_or_404(PriceListEntry, pk=pk)
    if company and entry.price_list.company != company:
        return redirect('pricing:pricing_dashboard')
    pl_pk = entry.price_list.pk
    entry.delete()
    messages.success(request, _t('entry_deleted', _lang(request)))
    return redirect('pricing:price_list_detail', pk=pl_pk)


# ============================================================
# PROMOTIONS
# ============================================================

@login_required
@never_cache
def promotion_list(request):
    company = _get_company(request)
    q = request.GET.get('search', '')
    status_f = request.GET.get('status', '')

    promos = Promotion.objects.filter(company=company) if company else Promotion.objects.all()
    if q:
        promos = promos.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if status_f:
        promos = promos.filter(status=status_f)
    promos = promos.order_by('-priority', 'name')

    paginator = Paginator(promos, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'pricing/promotion_list.html', {'page': page, 'search': q, 'status_filter': status_f})


@login_required
@never_cache
def promotion_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            promo = Promotion(
                company=company,
                name=name,
                code=request.POST.get('code', ''),
                description=request.POST.get('description', ''),
                discount_type=request.POST.get('discount_type', 'percentage'),
                discount_value=Decimal(request.POST.get('discount_value', '0') or '0'),
                status=request.POST.get('status', 'active'),
                priority=int(request.POST.get('priority', 0)),
                combine_with=request.POST.get('combine_with', 'none'),
                min_order_total=Decimal(request.POST.get('min_order_total', '0') or '0'),
                min_quantity=int(request.POST.get('min_quantity', 1)),
                buy_quantity=int(request.POST.get('buy_quantity', 1)),
                free_quantity=int(request.POST.get('free_quantity', 1)),
            )
            max_uses = request.POST.get('max_total_uses')
            if max_uses:
                promo.max_total_uses = int(max_uses)
            max_pc = request.POST.get('max_per_customer')
            if max_pc:
                promo.max_per_customer = int(max_pc)
            sd = request.POST.get('start_date')
            ed = request.POST.get('end_date')
            if sd:
                promo.start_date = sd
            if ed:
                promo.end_date = ed
            promo.save()

            product_ids = request.POST.getlist('applicable_products')
            if product_ids:
                promo.applicable_products.set(product_ids)
            segment_ids = request.POST.getlist('applicable_segments')
            if segment_ids:
                from crm.models import CustomerSegment
                promo.applicable_segments.set(segment_ids)
            customer_ids = request.POST.getlist('applicable_customers')
            if customer_ids:
                promo.applicable_customers.set(customer_ids)

            messages.success(request, _t('promotion_created', lang))
            return redirect('pricing:promotion_list')
        messages.error(request, _t('fill_required_fields', lang))

    from crm.models import CustomerSegment
    ctx = {
        'products': Product.objects.all(),
        'segments': CustomerSegment.objects.filter(company=company) if company else [],
        'customers': Customer.objects.filter(company=company) if company else Customer.objects.all(),
    }
    return render(request, 'pricing/promotion_form.html', ctx)


@login_required
@never_cache
def promotion_edit(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    promo = get_object_or_404(Promotion, pk=pk)
    if company and promo.company != company:
        return redirect('pricing:pricing_dashboard')

    if request.method == 'POST':
        promo.name = request.POST.get('name', promo.name)
        promo.code = request.POST.get('code', promo.code)
        promo.description = request.POST.get('description', '')
        promo.discount_type = request.POST.get('discount_type', promo.discount_type)
        promo.discount_value = Decimal(request.POST.get('discount_value', str(promo.discount_value)) or '0')
        promo.status = request.POST.get('status', promo.status)
        promo.priority = int(request.POST.get('priority', promo.priority))
        promo.combine_with = request.POST.get('combine_with', promo.combine_with)
        promo.min_order_total = Decimal(request.POST.get('min_order_total', str(promo.min_order_total)) or '0')
        promo.min_quantity = int(request.POST.get('min_quantity', promo.min_quantity))
        promo.buy_quantity = int(request.POST.get('buy_quantity', promo.buy_quantity))
        promo.free_quantity = int(request.POST.get('free_quantity', promo.free_quantity))
        max_uses = request.POST.get('max_total_uses')
        promo.max_total_uses = int(max_uses) if max_uses else None
        max_pc = request.POST.get('max_per_customer')
        promo.max_per_customer = int(max_pc) if max_pc else None
        sd = request.POST.get('start_date')
        ed = request.POST.get('end_date')
        promo.start_date = sd if sd else None
        promo.end_date = ed if ed else None
        promo.save()

        product_ids = request.POST.getlist('applicable_products')
        promo.applicable_products.set(product_ids or [])
        segment_ids = request.POST.getlist('applicable_segments')
        promo.applicable_segments.set(segment_ids or [])
        customer_ids = request.POST.getlist('applicable_customers')
        promo.applicable_customers.set(customer_ids or [])

        messages.success(request, _t('promotion_updated', lang))
        return redirect('pricing:promotion_list')

    from crm.models import CustomerSegment
    ctx = {
        'promo': promo,
        'products': Product.objects.all(),
        'segments': CustomerSegment.objects.filter(company=company) if company else [],
        'customers': Customer.objects.filter(company=company) if company else Customer.objects.all(),
    }
    return render(request, 'pricing/promotion_form.html', ctx)


@login_required
@require_POST
@never_cache
def promotion_delete(request, pk):
    company = _get_company(request)
    promo = get_object_or_404(Promotion, pk=pk)
    if company and promo.company != company:
        return redirect('pricing:pricing_dashboard')
    promo.delete()
    messages.success(request, _t('promotion_deleted', _lang(request)))
    return redirect('pricing:promotion_list')


# ============================================================
# COUPONS
# ============================================================

@login_required
@never_cache
def coupon_list(request):
    company = _get_company(request)
    q = request.GET.get('search', '')
    coupons = Coupon.objects.filter(company=company) if company else Coupon.objects.all()
    if q:
        coupons = coupons.filter(Q(code__icontains=q) | Q(name__icontains=q))
    coupons = coupons.order_by('-created_at')
    paginator = Paginator(coupons, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'pricing/coupon_list.html', {'page': page, 'search': q})


@login_required
@never_cache
def coupon_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        name = request.POST.get('name', '').strip()
        if code and name:
            coupon = Coupon(
                company=company,
                code=code,
                name=name,
                discount_type=request.POST.get('discount_type', 'percentage'),
                discount_value=Decimal(request.POST.get('discount_value', '0') or '0'),
                max_per_customer=int(request.POST.get('max_per_customer', 1)),
                min_order_total=Decimal(request.POST.get('min_order_total', '0') or '0'),
                is_active=request.POST.get('is_active', 'on') == 'on',
            )
            max_d = request.POST.get('max_discount_amount')
            if max_d:
                coupon.max_discount_amount = Decimal(max_d)
            max_uses = request.POST.get('max_total_uses')
            if max_uses:
                coupon.max_total_uses = int(max_uses)
            sd = request.POST.get('start_date')
            ed = request.POST.get('end_date')
            if sd:
                coupon.start_date = sd
            if ed:
                coupon.end_date = ed
            coupon.save()
            messages.success(request, _t('coupon_created', lang))
            return redirect('pricing:coupon_list')
        messages.error(request, _t('fill_required_fields', lang))

    ctx = {
        'products': Product.objects.all(),
        'categories': Category.objects.all(),
    }
    return render(request, 'pricing/coupon_form.html', ctx)


@login_required
@never_cache
def coupon_edit(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    coupon = get_object_or_404(Coupon, pk=pk)
    if company and coupon.company != company:
        return redirect('pricing:pricing_dashboard')

    if request.method == 'POST':
        coupon.code = request.POST.get('code', coupon.code).strip().upper()
        coupon.name = request.POST.get('name', coupon.name)
        coupon.discount_type = request.POST.get('discount_type', coupon.discount_type)
        coupon.discount_value = Decimal(request.POST.get('discount_value', str(coupon.discount_value)) or '0')
        coupon.max_per_customer = int(request.POST.get('max_per_customer', coupon.max_per_customer))
        coupon.min_order_total = Decimal(request.POST.get('min_order_total', str(coupon.min_order_total)) or '0')
        coupon.is_active = request.POST.get('is_active', 'on') == 'on'
        max_d = request.POST.get('max_discount_amount')
        coupon.max_discount_amount = Decimal(max_d) if max_d else None
        max_uses = request.POST.get('max_total_uses')
        coupon.max_total_uses = int(max_uses) if max_uses else None
        sd = request.POST.get('start_date')
        ed = request.POST.get('end_date')
        coupon.start_date = sd if sd else None
        coupon.end_date = ed if ed else None
        coupon.save()
        messages.success(request, _t('coupon_updated', lang))
        return redirect('pricing:coupon_list')

    ctx = {'coupon': coupon}
    return render(request, 'pricing/coupon_form.html', ctx)


@login_required
@require_POST
@never_cache
def coupon_delete(request, pk):
    company = _get_company(request)
    coupon = get_object_or_404(Coupon, pk=pk)
    if company and coupon.company != company:
        return redirect('pricing:pricing_dashboard')
    coupon.delete()
    messages.success(request, _t('coupon_deleted', _lang(request)))
    return redirect('pricing:coupon_list')


# ============================================================
# CUSTOMER-SPECIFIC PRICES
# ============================================================

@login_required
@never_cache
def customer_price_list(request):
    company = _get_company(request)
    q = request.GET.get('search', '')
    cps = CustomerSpecificPrice.objects.filter(company=company).select_related('customer', 'product') if company else CustomerSpecificPrice.objects.select_related('customer', 'product').all()
    if q:
        cps = cps.filter(Q(customer__name__icontains=q) | Q(product__name__icontains=q))
    cps = cps.order_by('-priority', 'customer__name')
    paginator = Paginator(cps, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'pricing/customer_price_list.html', {'page': page, 'search': q})


@login_required
@never_cache
def customer_price_create(request):
    company = _get_company(request)
    lang = _lang(request)
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        product_id = request.POST.get('product')
        price = request.POST.get('price')
        if customer_id and product_id and price:
            old_price = None
            product = Product.objects.get(pk=product_id)
            try:
                old_price = product.price
            except Exception:
                pass
            cp = CustomerSpecificPrice(
                company=company,
                customer=Customer.objects.get(pk=customer_id),
                product=product,
                price=Decimal(price),
                min_quantity=int(request.POST.get('min_quantity', 1)),
                max_quantity=int(request.POST['max_quantity']) if request.POST.get('max_quantity') else None,
                currency=request.POST.get('currency', 'UZS'),
                priority=int(request.POST.get('priority', 100)),
                is_active=request.POST.get('is_active', 'on') == 'on',
            )
            sd = request.POST.get('start_date')
            ed = request.POST.get('end_date')
            if sd:
                cp.start_date = sd
            if ed:
                cp.end_date = ed
            cp.save()

            PriceHistory.objects.create(
                company=company,
                product=product,
                old_price=old_price or Decimal('0'),
                new_price=cp.price,
                change_type='customer_price',
                reason=f'Customer-specific price for {cp.customer.name}',
                changed_by=request.user,
            )
            messages.success(request, _t('customer_price_created', lang))
            return redirect('pricing:customer_price_list')

    ctx = {
        'customers': Customer.objects.filter(company=company) if company else Customer.objects.all(),
        'products': Product.objects.all(),
    }
    return render(request, 'pricing/customer_price_form.html', ctx)


@login_required
@never_cache
def customer_price_edit(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    cp = get_object_or_404(CustomerSpecificPrice, pk=pk)
    if company and cp.company != company:
        return redirect('pricing:pricing_dashboard')

    if request.method == 'POST':
        old_price = cp.price
        cp.price = Decimal(request.POST.get('price', str(cp.price)) or '0')
        cp.min_quantity = int(request.POST.get('min_quantity', cp.min_quantity))
        mq = request.POST.get('max_quantity')
        cp.max_quantity = int(mq) if mq else None
        cp.priority = int(request.POST.get('priority', cp.priority))
        cp.is_active = request.POST.get('is_active', 'on') == 'on'
        sd = request.POST.get('start_date')
        ed = request.POST.get('end_date')
        cp.start_date = sd if sd else None
        cp.end_date = ed if ed else None
        cp.save()

        PriceHistory.objects.create(
            company=company or cp.company,
            product=cp.product,
            old_price=old_price,
            new_price=cp.price,
            change_type='customer_price',
            reason=f'Updated customer price for {cp.customer.name}',
            changed_by=request.user,
        )
        messages.success(request, _t('customer_price_updated', lang))
        return redirect('pricing:customer_price_list')

    ctx = {
        'cp': cp,
        'customers': Customer.objects.filter(company=company) if company else Customer.objects.all(),
        'products': Product.objects.all(),
    }
    return render(request, 'pricing/customer_price_form.html', ctx)


@login_required
@require_POST
@never_cache
def customer_price_delete(request, pk):
    company = _get_company(request)
    cp = get_object_or_404(CustomerSpecificPrice, pk=pk)
    if company and cp.company != company:
        return redirect('pricing:pricing_dashboard')
    cp.delete()
    messages.success(request, _t('customer_price_deleted', _lang(request)))
    return redirect('pricing:customer_price_list')


# ============================================================
# PRICE HISTORY
# ============================================================

@login_required
@never_cache
def price_history(request):
    company = _get_company(request)
    q = request.GET.get('search', '')
    change_type = request.GET.get('type', '')

    history = PriceHistory.objects.filter(company=company).select_related('product', 'price_list', 'changed_by') if company else PriceHistory.objects.select_related('product', 'changed_by').all()
    if q:
        history = history.filter(Q(product__name__icontains=q))
    if change_type:
        history = history.filter(change_type=change_type)
    history = history.order_by('-changed_at')

    paginator = Paginator(history, 30)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'pricing/price_history.html', {'page': page, 'search': q, 'type_filter': change_type})


# ============================================================
# PRICING SIMULATOR
# ============================================================

@login_required
@never_cache
def pricing_simulator(request):
    company = _get_company(request)
    lang = _lang(request)
    result = None
    explanation = []

    if request.method == 'POST' or request.GET.get('product'):
        product_id = request.POST.get('product') or request.GET.get('product')
        customer_id = request.POST.get('customer')
        quantity = request.POST.get('quantity', '1')
        coupon_code = request.POST.get('coupon_code', '')
        channel = request.POST.get('channel', '')

        if product_id:
            try:
                product = Product.objects.get(pk=product_id)
                customer = None
                if customer_id:
                    customer = Customer.objects.get(pk=customer_id)
                qty = Decimal(quantity or '1')

                price_result = resolve_price(
                    company=company,
                    product=product,
                    customer=customer,
                    quantity=qty,
                    channel=channel,
                    coupon_code=coupon_code if coupon_code else None,
                )
                result = price_result
                explanation = price_result.explanation
            except (Product.DoesNotExist, Customer.DoesNotExist, InvalidOperation):
                messages.error(request, _t('invalid_input', lang))

    ctx = {
        'result': result,
        'explanation': explanation,
        'products': Product.objects.all(),
        'customers': Customer.objects.filter(company=company) if company else Customer.objects.all(),
        'selected_product': request.POST.get('product') or request.GET.get('product', ''),
        'selected_customer': request.POST.get('customer', ''),
        'selected_quantity': request.POST.get('quantity', '1'),
        'selected_coupon': request.POST.get('coupon_code', ''),
        'selected_channel': request.POST.get('channel', ''),
    }
    return render(request, 'pricing/simulator.html', ctx)


# ============================================================
# API
# ============================================================

@login_required
def api_resolve_price(request):
    company = _get_company(request)
    product_id = request.GET.get('product_id')
    customer_id = request.GET.get('customer_id')
    quantity = request.GET.get('quantity', '1')
    coupon_code = request.GET.get('coupon_code', '')
    channel = request.GET.get('channel', '')

    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    try:
        product = Product.objects.get(pk=product_id)
        customer = None
        if customer_id:
            customer = Customer.objects.get(pk=customer_id)
        qty = Decimal(quantity)
        price_result = resolve_price(
            company=company, product=product, customer=customer,
            quantity=qty, channel=channel,
            coupon_code=coupon_code if coupon_code else None,
        )
        return JsonResponse({
            'base_price': str(price_result.base_price),
            'final_price': str(price_result.final_price),
            'discount_amount': str(price_result.discount_amount),
            'currency': price_result.currency,
            'price_list': price_result.price_list_name,
            'applied_rule': price_result.applied_rule,
            'promo_discount': str(price_result.promo_discount),
            'coupon_discount': str(price_result.coupon_discount),
            'explanation': price_result.explanation,
        })
    except (Product.DoesNotExist, Customer.DoesNotExist, InvalidOperation) as e:
        return JsonResponse({'error': str(e)}, status=400)
