from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import GTIN, MarkingCode, MarkingCodeHistory, Aggregation, AggregationItem, CodeValidation
from .forms import GTINForm, MarkingCodeForm, AggregationForm, CodeValidateForm


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if company:
        return company
    if request.user.is_superuser:
        from django.contrib import messages as _msgs
        _msgs.warning(request, 'Superuser: no company assigned. Showing first company data.')
        from users.models import Company
        return Company.objects.first()
    return None


# ==========================================
# DASHBOARD
# ==========================================

@login_required
@never_cache
def marking_dashboard(request):
    company = _get_company(request)
    if not company and not request.user.is_superuser:
        messages.error(request, 'No company assigned')
        return redirect('login')

    codes = MarkingCode.objects.filter(company=company) if company else MarkingCode.objects.all()

    now = timezone.now()
    stats = {
        'total': codes.count(),
        'verified': codes.filter(verification_status='internal_verified').count(),
        'sold': codes.filter(status='sold').count(),
        'returned': codes.filter(status='returned').count(),
        'expired': codes.filter(status='cancelled').count(),
        'expiring_soon': codes.filter(
            status='in_stock',
            created_at__gte=now - timedelta(days=180),
            created_at__lte=now - timedelta(days=90),
        ).count(),
        'quarantined': codes.filter(status='quarantined').count(),
    }

    recent_history = MarkingCodeHistory.objects.filter(
        company=company
    ).select_related('marking_code', 'performed_by')[:20]

    context = {
        'company': company,
        'stats': stats,
        'recent_history': recent_history,
    }
    return render(request, 'markings/dashboard.html', context)


# ==========================================
# GTIN VIEWS
# ==========================================

@login_required
@never_cache
def gtin_list(request):
    company = _get_company(request)
    search = request.GET.get('search', '')

    gtins = GTIN.objects.filter(company=company).select_related('product') if company else GTIN.objects.select_related('product')

    if search:
        gtins = gtins.filter(
            Q(gtin__icontains=search) | Q(product__name__icontains=search)
        )

    gtins = gtins.order_by('-created_at')
    paginator = Paginator(gtins, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'company': company,
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'markings/gtin_list.html', context)


@login_required
@never_cache
def gtin_create(request):
    company = _get_company(request)

    if request.method == 'POST':
        form = GTINForm(request.POST)
        if form.is_valid():
            gtin = form.save(commit=False)
            gtin.company = company
            gtin.save()
            messages.success(request, f'GTIN {gtin.gtin} created successfully')
            return redirect('markings:gtin_detail', pk=gtin.pk)
    else:
        form = GTINForm()

    context = {
        'company': company,
        'form': form,
    }
    return render(request, 'markings/gtin_form.html', context)


@login_required
@never_cache
def gtin_detail(request, pk):
    company = _get_company(request)
    gtin = get_object_or_404(GTIN, pk=pk, company=company)
    marking_codes = MarkingCode.objects.filter(gtin=gtin, company=company).select_related('product', 'warehouse')

    context = {
        'company': company,
        'gtin': gtin,
        'marking_codes': marking_codes,
    }
    return render(request, 'markings/gtin_detail.html', context)


# ==========================================
# MARKING CODE VIEWS
# ==========================================

@login_required
@never_cache
def marking_list(request):
    company = _get_company(request)
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    codes = MarkingCode.objects.filter(company=company).select_related(
        'product', 'gtin', 'warehouse', 'batch'
    ) if company else MarkingCode.objects.select_related('product', 'gtin', 'warehouse', 'batch')

    if search:
        codes = codes.filter(
            Q(code__icontains=search) |
            Q(product__name__icontains=search) |
            Q(serial_number__icontains=search)
        )

    if status_filter:
        codes = codes.filter(status=status_filter)

    codes = codes.order_by('-created_at')
    paginator = Paginator(codes, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    status_choices = MarkingCode.STATUS_CHOICES

    context = {
        'company': company,
        'page_obj': page_obj,
        'search': search,
        'status_filter': status_filter,
        'status_choices': status_choices,
    }
    return render(request, 'markings/marking_list.html', context)


@login_required
@never_cache
def marking_create(request):
    company = _get_company(request)

    if request.method == 'POST':
        form = MarkingCodeForm(request.POST)
        if form.is_valid():
            code = form.save(commit=False)
            code.company = company
            code.created_by = request.user
            code.save()
            MarkingCodeHistory.objects.create(
                company=company,
                marking_code=code,
                from_status=None,
                to_status=code.status,
                event_type='created',
                performed_by=request.user,
            )
            messages.success(request, f'Marking code {code.code} created successfully')
            return redirect('markings:marking_detail', pk=code.pk)
    else:
        form = MarkingCodeForm()

    context = {
        'company': company,
        'form': form,
    }
    return render(request, 'markings/marking_form.html', context)


@login_required
@never_cache
def marking_detail(request, pk):
    company = _get_company(request)
    code = get_object_or_404(
        MarkingCode.objects.select_related('product', 'gtin', 'warehouse', 'location', 'batch',
                                           'supplier', 'purchase', 'sale', 'customer'),
        pk=pk, company=company,
    )
    history = MarkingCodeHistory.objects.filter(
        marking_code=code, company=company
    ).select_related('performed_by', 'warehouse', 'location').order_by('-performed_at')

    context = {
        'company': company,
        'code': code,
        'history': history,
    }
    return render(request, 'markings/marking_detail.html', context)


@login_required
@require_POST
def marking_verify(request, pk):
    company = _get_company(request)
    code = get_object_or_404(MarkingCode, pk=pk, company=company)

    verification_status = request.POST.get('verification_status', 'internal_verified')
    verification_notes = request.POST.get('verification_notes', '')

    valid_statuses = ['not_verified', 'internal_verified', 'external_verified', 'rejected']
    if verification_status in valid_statuses:
        old_status = code.verification_status
        code.verification_status = verification_status
        code.verification_notes = verification_notes
        code.save()
        MarkingCodeHistory.objects.create(
            company=company,
            marking_code=code,
            from_status=code.status,
            to_status=code.status,
            event_type='verified',
            notes=f'Verification changed from {old_status} to {verification_status}. {verification_notes}'.strip(),
            performed_by=request.user,
        )
        messages.success(request, f'Code {code.code} verification updated to {verification_status}')
    else:
        messages.error(request, 'Invalid verification status')

    return redirect('markings:marking_detail', pk=pk)


@login_required
@never_cache
def marking_history(request, pk):
    company = _get_company(request)
    code = get_object_or_404(MarkingCode, pk=pk, company=company)
    history = MarkingCodeHistory.objects.filter(
        marking_code=code, company=company
    ).select_related('performed_by', 'warehouse', 'location').order_by('-performed_at')

    paginator = Paginator(history, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'company': company,
        'code': code,
        'page_obj': page_obj,
    }
    return render(request, 'markings/marking_history.html', context)


# ==========================================
# AGGREGATION VIEWS
# ==========================================

@login_required
@never_cache
def aggregation_list(request):
    company = _get_company(request)
    search = request.GET.get('search', '')

    aggregations = Aggregation.objects.filter(company=company).select_related('product', 'warehouse') if company \
        else Aggregation.objects.select_related('product', 'warehouse')

    if search:
        aggregations = aggregations.filter(
            Q(parent_code__icontains=search) | Q(product__name__icontains=search)
        )

    aggregations = aggregations.order_by('-created_at')
    paginator = Paginator(aggregations, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'company': company,
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'markings/aggregation_list.html', context)


@login_required
@never_cache
def aggregation_create(request):
    company = _get_company(request)

    if request.method == 'POST':
        form = AggregationForm(request.POST)
        if form.is_valid():
            agg = form.save(commit=False)
            agg.company = company
            agg.created_by = request.user
            agg.save()
            messages.success(request, f'Aggregation {agg.parent_code} created successfully')
            return redirect('markings:aggregation_detail', pk=agg.pk)
    else:
        form = AggregationForm()

    context = {
        'company': company,
        'form': form,
    }
    return render(request, 'markings/aggregation_form.html', context)


@login_required
@never_cache
def aggregation_detail(request, pk):
    company = _get_company(request)
    aggregation = get_object_or_404(
        Aggregation.objects.select_related('product', 'warehouse', 'location'),
        pk=pk, company=company,
    )
    items = AggregationItem.objects.filter(
        aggregation=aggregation, company=company
    ).select_related('marking_code', 'marking_code__product')

    context = {
        'company': company,
        'aggregation': aggregation,
        'items': items,
    }
    return render(request, 'markings/aggregation_detail.html', context)


@login_required
@require_POST
def aggregation_disaggregate(request, pk):
    company = _get_company(request)
    aggregation = get_object_or_404(Aggregation, pk=pk, company=company)

    if aggregation.status != 'active':
        messages.error(request, 'Only active aggregations can be disaggregated')
        return redirect('markings:aggregation_detail', pk=pk)

    aggregation.status = 'disaggregated'
    aggregation.save()

    items = AggregationItem.objects.filter(aggregation=aggregation, company=company).select_related('marking_code')
    for item in items:
        item.marking_code.status = 'in_stock'
        item.marking_code.save()
        MarkingCodeHistory.objects.create(
            company=company,
            marking_code=item.marking_code,
            from_status='reserved',
            to_status='in_stock',
            event_type='disaggregated',
            notes=f'Released from aggregation {aggregation.parent_code}',
            performed_by=request.user,
        )

    messages.success(request, f'Aggregation {aggregation.parent_code} disaggregated successfully')
    return redirect('markings:aggregation_detail', pk=pk)


# ==========================================
# CODE VALIDATION
# ==========================================

@login_required
@never_cache
def code_validate(request):
    company = _get_company(request)
    form = CodeValidateForm(request.GET or None)
    result = None

    if form.is_valid():
        code_input = form.cleaned_data['code_input'].strip()
        result = _validate_code(company, request.user, code_input)

    context = {
        'company': company,
        'form': form,
        'result': result,
    }
    return render(request, 'markings/code_validate.html', context)


@login_required
def code_validate_api(request):
    company = _get_company(request)
    code_input = request.GET.get('code', '').strip()

    if not code_input:
        return JsonResponse({'error': 'No code provided'}, status=400)

    result = _validate_code(company, request.user, code_input)
    return JsonResponse(result)


def _validate_code(company, user, code_input):
    if not code_input:
        return {'result': 'unknown', 'message': 'No code entered'}

    gtin = GTIN.objects.filter(company=company, gtin=code_input).select_related('product').first()
    if gtin:
        validation = CodeValidation.objects.create(
            company=company,
            code_input=code_input,
            code_type='gtin',
            result='valid',
            resolved_product=gtin.product,
            gtin=gtin,
            verified_by=user,
        )
        return {
            'result': 'valid',
            'code_type': 'gtin',
            'product': str(gtin.product),
            'product_id': gtin.product.pk,
            'gtin': gtin.gtin,
            'validation_id': validation.pk,
        }

    marking = MarkingCode.objects.filter(
        company=company, code=code_input
    ).select_related('product', 'warehouse', 'sale').first()

    if marking:
        result = 'valid'
        if marking.status == 'sold':
            result = 'already_sold'
        elif marking.status == 'cancelled':
            result = 'expired'

        validation = CodeValidation.objects.create(
            company=company,
            code_input=code_input,
            code_type='marking',
            result=result,
            resolved_product=marking.product,
            marking_code=marking,
            verified_by=user,
        )
        return {
            'result': result,
            'code_type': 'marking',
            'product': str(marking.product),
            'product_id': marking.product.pk,
            'status': marking.status,
            'verification_status': marking.verification_status,
            'warehouse': str(marking.warehouse) if marking.warehouse else None,
            'validation_id': validation.pk,
        }

    serial_match = MarkingCode.objects.filter(
        company=company, serial_number=code_input
    ).select_related('product').first()

    if serial_match:
        validation = CodeValidation.objects.create(
            company=company,
            code_input=code_input,
            code_type='serial',
            result='valid',
            resolved_product=serial_match.product,
            marking_code=serial_match,
            verified_by=user,
        )
        return {
            'result': 'valid',
            'code_type': 'serial',
            'product': str(serial_match.product),
            'product_id': serial_match.product.pk,
            'validation_id': validation.pk,
        }

    from products.models import Product
    barcode_match = Product.objects.filter(
        company=company, barcode=code_input
    ).first()

    if barcode_match:
        validation = CodeValidation.objects.create(
            company=company,
            code_input=code_input,
            code_type='barcode',
            result='valid',
            resolved_product=barcode_match,
            verified_by=user,
        )
        return {
            'result': 'valid',
            'code_type': 'barcode',
            'product': str(barcode_match),
            'product_id': barcode_match.pk,
            'validation_id': validation.pk,
        }

    CodeValidation.objects.create(
        company=company,
        code_input=code_input,
        code_type='marking',
        result='unknown',
        verified_by=user,
    )
    return {'result': 'unknown', 'message': 'Code not found in system'}


# ==========================================
# TRACEABILITY
# ==========================================

@login_required
@never_cache
def trace_product(request):
    company = _get_company(request)
    form = CodeValidateForm(request.GET or None)
    timeline = None
    search_code = ''

    if form.is_valid():
        search_code = form.cleaned_data['code_input'].strip()
        marking = MarkingCode.objects.filter(
            company=company, code=search_code
        ).select_related('product', 'gtin', 'warehouse', 'location', 'batch',
                         'supplier', 'purchase', 'sale', 'customer').first()

        if not marking:
            marking = MarkingCode.objects.filter(
                company=company, serial_number=search_code
            ).select_related('product', 'gtin', 'warehouse', 'location', 'batch',
                             'supplier', 'purchase', 'sale', 'customer').first()

        if marking:
            events = MarkingCodeHistory.objects.filter(
                marking_code=marking, company=company
            ).select_related('performed_by', 'warehouse', 'location').order_by('performed_at')

            timeline = {
                'marking_code': marking,
                'product': marking.product,
                'events': events,
            }

    context = {
        'company': company,
        'form': form,
        'timeline': timeline,
        'search_code': search_code,
    }
    return render(request, 'markings/trace_product.html', context)


@login_required
@never_cache
def traceability_timeline(request, product_id):
    company = _get_company(request)
    from products.models import Product
    product = get_object_or_404(Product, pk=product_id, company=company)

    marking_codes = MarkingCode.objects.filter(
        product=product, company=company
    ).select_related('gtin', 'warehouse', 'location', 'batch',
                     'supplier', 'purchase', 'sale', 'customer')

    events = MarkingCodeHistory.objects.filter(
        marking_code__product=product, company=company
    ).select_related('marking_code', 'performed_by', 'warehouse', 'location').order_by('-performed_at')

    paginator = Paginator(events, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'company': company,
        'product': product,
        'marking_codes': marking_codes,
        'page_obj': page_obj,
    }
    return render(request, 'markings/traceability_timeline.html', context)
