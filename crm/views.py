from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.db.models import Sum, Count, Q, Avg, F, Max
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal
from sales.models import Customer, Sale, SaleItem, SaleReturn, SalePayment
from orders.models import Order
from contacts.models import Contact
from users.models import Company
from core.translations import get_translation
from .models import (
    CustomerSegment, CustomerTag, CustomerSegmentAssignment,
    CustomerTagAssignment, CustomerCommunication, CustomerNote,
    CustomerDocument, CustomerTask,
)


def _lang(request):
    return request.session.get('language', 'uz')


def _get_company(request):
    company = getattr(request.user, 'company', None)
    if not company and not request.user.is_superuser:
        return None
    return company


# ============================================================
# CRM DASHBOARD
# ============================================================

@login_required
@never_cache
def crm_dashboard(request):
    company = _get_company(request)
    lang = _lang(request)

    if company:
        customers = Customer.objects.filter(company=company)
        sales = Sale.objects.filter(company=company)
        orders = Order.objects.filter(company=company)
        segments = CustomerSegment.objects.filter(company=company)
    else:
        customers = Customer.objects.all()
        sales = Sale.objects.all()
        orders = Order.objects.all()
        segments = CustomerSegment.objects.all()

    today = timezone.now().date()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    thirty_days_ago = today - timedelta(days=30)
    ninety_days_ago = today - timedelta(days=90)

    total_customers = customers.count()
    new_customers_month = customers.filter(created_at__date__gte=month_start).count()
    active_customers = customers.filter(is_active=True, customer_status='active').count()
    inactive_customers = customers.filter(is_active=True, customer_status='inactive').count()
    blocked_customers = customers.filter(customer_status='blocked').count()
    prospect_customers = customers.filter(customer_status='prospect').count()

    total_revenue = sales.filter(status='completed').aggregate(t=Sum('total'))['t'] or 0
    revenue_month = sales.filter(status='completed', created_at__date__gte=month_start).aggregate(t=Sum('total'))['t'] or 0
    total_outstanding = sales.exclude(payment_status='paid').aggregate(t=Sum('total'))['t'] or 0
    overdue_debt = sales.filter(payment_status='overdue').aggregate(t=Sum('total'))['t'] or 0
    avg_order_value = sales.filter(status='completed').aggregate(a=Avg('total'))['a'] or 0

    top_customers = customers.annotate(
        order_count_c=Count('sales'),
        total_value=Sum('sales__total'),
    ).filter(order_count_c__gt=0).order_by('-total_value')[:10]

    recent_customers = customers.order_by('-created_at')[:10]

    new_vs_returning = sales.filter(
        status='completed',
        created_at__date__gte=year_start,
    ).values('customer').annotate(order_count=Count('id')).order_by()
    new_count = sum(1 for c in new_vs_returning if c['order_count'] == 1)
    returning_count = sum(1 for c in new_vs_returning if c['order_count'] > 1)

    action_customers = customers.filter(
        customer_status='active',
        is_active=True,
    ).annotate(
        last_order_date=Max('sales__created_at'),
    ).filter(
        last_order_date__lt=thirty_days_ago,
        last_order_date__gte=ninety_days_ago,
    )[:10]

    overdue_tasks = CustomerTask.objects.filter(
        company=company,
        status__in=['pending', 'in_progress'],
        due_date__lt=today,
    ).select_related('customer')[:10] if company else CustomerTask.objects.none()

    context = {
        'total_customers': total_customers,
        'new_customers_month': new_customers_month,
        'active_customers': active_customers,
        'inactive_customers': inactive_customers,
        'blocked_customers': blocked_customers,
        'prospect_customers': prospect_customers,
        'total_revenue': total_revenue,
        'revenue_month': revenue_month,
        'total_outstanding': total_outstanding,
        'overdue_debt': overdue_debt,
        'avg_order_value': avg_order_value,
        'top_customers': top_customers,
        'recent_customers': recent_customers,
        'new_customers_count': new_count,
        'returning_customers_count': returning_count,
        'at_risk_customers': action_customers,
        'overdue_tasks': overdue_tasks,
        'segments': segments,
    }
    return render(request, 'crm/crm_dashboard.html', context)


# ============================================================
# CUSTOMER LIST (ENHANCED)
# ============================================================

@login_required
@never_cache
def customer_crm_list(request):
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
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('customer_type', '')
    segment_filter = request.GET.get('segment', '')
    tag_filter = request.GET.get('tag', '')
    city_filter = request.GET.get('city', '')
    sort = request.GET.get('sort', '-created_at')

    if q:
        customers = customers.filter(
            Q(name__icontains=q) |
            Q(contact_person__icontains=q) |
            Q(phone__icontains=q) |
            Q(email__icontains=q) |
            Q(telegram__icontains=q) |
            Q(company_name__icontains=q) |
            Q(tax_id__icontains=q) |
            Q(city__icontains=q)
        )
    if status_filter:
        customers = customers.filter(customer_status=status_filter)
    if type_filter:
        customers = customers.filter(customer_type=type_filter)
    if segment_filter:
        customers = customers.filter(segment_assignments__segment_id=segment_filter)
    if tag_filter:
        customers = customers.filter(tag_assignments__tag_id=tag_filter)
    if city_filter:
        customers = customers.filter(city__icontains=city_filter)

    allowed_sorts = {
        'name': 'name', '-name': '-name',
        'created_at': 'created_at', '-created_at': '-created_at',
        'last_purchase_date': 'last_purchase_date', '-last_purchase_date': '-last_purchase_date',
        'total_lifetime_value': 'total_lifetime_value', '-total_lifetime_value': '-total_lifetime_value',
    }
    customers = customers.annotate(
        sale_count_a=Count('sales'),
        total_revenue_a=Sum('sales__total'),
    ).order_by(allowed_sorts.get(sort, '-created_at'))

    customers = customers.distinct()

    paginator = Paginator(customers, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    segments = CustomerSegment.objects.filter(company=company, is_active=True) if company else CustomerSegment.objects.filter(is_active=True)
    tags = CustomerTag.objects.filter(company=company) if company else CustomerTag.objects.all()
    cities = Customer.objects.filter(company=company).exclude(city='').values_list('city', flat=True).distinct() if company else Customer.objects.exclude(city='').values_list('city', flat=True).distinct()

    context = {
        'page_obj': page_obj,
        'q': q,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'segment_filter': segment_filter,
        'tag_filter': tag_filter,
        'city_filter': city_filter,
        'sort': sort,
        'segments': segments,
        'tags': tags,
        'cities': sorted(set(cities)),
        'status_choices': Customer.CUSTOMER_STATUS_CHOICES if hasattr(Customer, 'CUSTOMER_STATUS_CHOICES') else [],
        'total_count': paginator.count,
    }
    return render(request, 'crm/customer_crm_list.html', context)


# ============================================================
# CUSTOMER 360 VIEW
# ============================================================

@login_required
@never_cache
def customer_360(request, pk):
    company = _get_company(request)
    lang = _lang(request)

    if company:
        customer = get_object_or_404(Customer, pk=pk, company=company)
    else:
        customer = get_object_or_404(Customer, pk=pk)

    tab = request.GET.get('tab', 'overview')

    orders = Order.objects.filter(customer=customer).select_related('warehouse').order_by('-created_at')
    sales = Sale.objects.filter(customer=customer).select_related('warehouse').order_by('-created_at')
    sale_returns = SaleReturn.objects.filter(customer=customer).order_by('-created_at')
    sale_payments = SalePayment.objects.filter(sale__customer=customer).select_related('sale').order_by('-created_at')

    communications = CustomerCommunication.objects.filter(customer=customer).select_related('created_by').order_by('-created_at')[:20]
    notes = CustomerNote.objects.filter(customer=customer).select_related('created_by').order_by('-created_at')
    tasks = CustomerTask.objects.filter(customer=customer).select_related('assigned_to', 'created_by').order_by('due_date')
    documents = CustomerDocument.objects.filter(customer=customer).select_related('created_by').order_by('-created_at')
    segments = CustomerSegmentAssignment.objects.filter(customer=customer).select_related('segment')
    tags = CustomerTagAssignment.objects.filter(customer=customer).select_related('tag')

    product_history = SaleItem.objects.filter(
        sale__customer=customer,
        sale__status='completed',
    ).values(
        'product__name', 'product__sku',
    ).annotate(
        total_qty=Sum('quantity'),
        total_spent=Sum('total'),
        avg_price=Avg('unit_price'),
        last_purchase=Max('sale__created_at'),
    ).order_by('-total_spent')[:20]

    recent_activity = []
    for sale in sales[:5]:
        recent_activity.append({
            'type': 'sale',
            'description': f"Sale {sale.reference} — ${sale.total}",
            'date': sale.created_at,
            'icon': 'bi-cart-check',
            'color': 'success',
            'url': f"/sales/{sale.pk}/",
        })
    for order in orders[:5]:
        recent_activity.append({
            'type': 'order',
            'description': f"Order {order.reference} — ${order.total}",
            'date': order.created_at,
            'icon': 'bi-receipt',
            'color': 'primary',
            'url': f"/orders/{order.pk}/",
        })
    for comm in communications[:5]:
        recent_activity.append({
            'type': 'communication',
            'description': f"{comm.get_comm_type_display()}: {comm.subject or comm.description[:50]}",
            'date': comm.created_at,
            'icon': 'bi-chat-dots',
            'color': 'info',
            'url': '#',
        })
    for note in notes[:5]:
        recent_activity.append({
            'type': 'note',
            'description': f"Note: {note.title or note.content[:50]}",
            'date': note.created_at,
            'icon': 'bi-journal-text',
            'color': 'warning',
            'url': '#',
        })
    recent_activity.sort(key=lambda x: x['date'], reverse=True)
    recent_activity = recent_activity[:15]

    total_revenue = customer.total_sales
    total_paid = customer.total_paid
    total_unpaid = customer.total_unpaid
    outstanding = customer.outstanding_balance
    avg_order = customer.average_order_value
    order_count = customer.order_count
    sale_count = customer.sale_count
    return_count = customer.return_count
    total_returns_val = customer.total_returns

    aging_buckets = {'current': 0, '1_7': 0, '8_30': 0, '31_60': 0, '61_90': 0, '90_plus': 0}
    unpaid_sales = sales.exclude(payment_status='paid').filter(status__in=['confirmed', 'shipped', 'completed'])
    today = timezone.now().date()
    for sale in unpaid_sales:
        due = sale.expected_delivery_date or sale.date
        days_overdue = (today - due).days
        outstanding_amt = sale.total - SalePayment.objects.filter(sale=sale).aggregate(t=Sum('amount'))['t'] or 0
        if outstanding_amt <= 0:
            continue
        if days_overdue <= 0:
            aging_buckets['current'] += outstanding_amt
        elif days_overdue <= 7:
            aging_buckets['1_7'] += outstanding_amt
        elif days_overdue <= 30:
            aging_buckets['8_30'] += outstanding_amt
        elif days_overdue <= 60:
            aging_buckets['31_60'] += outstanding_amt
        elif days_overdue <= 90:
            aging_buckets['61_90'] += outstanding_amt
        else:
            aging_buckets['90_plus'] += outstanding_amt

    rfm_score = None
    rfm_segment_name = None
    if customer.rfm_recency and customer.rfm_frequency and customer.rfm_monetary:
        rfm_score = customer.rfm_recency + customer.rfm_frequency + customer.rfm_monetary
        rfm_segment_name = customer.rfm_segment

    context = {
        'customer': customer,
        'tab': tab,
        'orders': orders,
        'sales': sales,
        'sale_returns': sale_returns,
        'sale_payments': sale_payments,
        'communications': communications,
        'notes': notes,
        'tasks': tasks,
        'documents': documents,
        'segments': segments,
        'tags': tags,
        'product_history': product_history,
        'recent_activity': recent_activity,
        'total_revenue': total_revenue,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
        'outstanding': outstanding,
        'avg_order': avg_order,
        'order_count': order_count,
        'sale_count': sale_count,
        'return_count': return_count,
        'total_returns_val': total_returns_val,
        'aging_buckets': aging_buckets,
        'rfm_score': rfm_score,
        'rfm_segment_name': rfm_segment_name,
    }
    return render(request, 'crm/customer_360.html', context)


# ============================================================
# CUSTOMER COMMUNICATION
# ============================================================

@login_required
@never_cache
def communication_create(request, customer_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=customer_id, company=company)
    else:
        customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':
        comm = CustomerCommunication.objects.create(
            company=company or customer.company,
            customer=customer,
            channel=request.POST.get('channel', 'phone'),
            comm_type=request.POST.get('comm_type', 'call'),
            subject=request.POST.get('subject', ''),
            description=request.POST.get('description', ''),
            outcome=request.POST.get('outcome', ''),
            direction=request.POST.get('direction', 'outbound'),
            status=request.POST.get('status', 'completed'),
            created_by=request.user,
        )
        if comm.status == 'completed':
            comm.completed_date = timezone.now()
            comm.save(update_fields=['completed_date'])
        messages.success(request, get_translation('communication_logged', lang))

    tab = request.GET.get('tab', 'communication')
    return redirect(f'/crm/{customer.pk}/?tab={tab}')


# ============================================================
# CUSTOMER NOTE
# ============================================================

@login_required
@never_cache
def note_create(request, customer_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=customer_id, company=company)
    else:
        customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':
        CustomerNote.objects.create(
            company=company or customer.company,
            customer=customer,
            category=request.POST.get('category', 'general'),
            title=request.POST.get('title', ''),
            content=request.POST.get('content', ''),
            is_important='is_important' in request.POST,
            created_by=request.user,
        )
        messages.success(request, get_translation('note_added', lang))

    tab = request.GET.get('tab', 'notes')
    return redirect(f'/crm/{customer.pk}/?tab={tab}')


@login_required
@never_cache
def note_delete(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        note = get_object_or_404(CustomerNote, pk=pk, company=company)
    else:
        note = get_object_or_404(CustomerNote, pk=pk)
    customer_id = note.customer_id
    if request.method == 'POST':
        note.delete()
        messages.success(request, get_translation('note_deleted', lang))
    return redirect(f'/crm/{customer_id}/?tab=notes')


# ============================================================
# CUSTOMER TASK
# ============================================================

@login_required
@never_cache
def task_create(request, customer_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=customer_id, company=company)
    else:
        customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':
        assigned_to_id = request.POST.get('assigned_to') or None
        CustomerTask.objects.create(
            company=company or customer.company,
            customer=customer,
            task_type=request.POST.get('task_type', 'other'),
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            priority=request.POST.get('priority', 'medium'),
            due_date=request.POST.get('due_date') or None,
            assigned_to_id=assigned_to_id,
            created_by=request.user,
        )
        messages.success(request, get_translation('task_created', lang))

    tab = request.GET.get('tab', 'tasks')
    return redirect(f'/crm/{customer.pk}/?tab={tab}')


@login_required
@never_cache
def task_update_status(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        task = get_object_or_404(CustomerTask, pk=pk, company=company)
    else:
        task = get_object_or_404(CustomerTask, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status', task.status)
        task.status = new_status
        if new_status == 'completed':
            task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at', 'updated_at'])
        messages.success(request, get_translation('task_updated', lang))

    return redirect(f'/crm/{task.customer_id}/?tab=tasks')


# ============================================================
# SEGMENT MANAGEMENT
# ============================================================

@login_required
@never_cache
def segment_list(request):
    company = _get_company(request)
    if company:
        segments = CustomerSegment.objects.filter(company=company).annotate(customer_count=Count('assignments__customer', distinct=True))
    else:
        segments = CustomerSegment.objects.all().annotate(customer_count=Count('assignments__customer', distinct=True))
    return render(request, 'crm/segment_list.html', {'segments': segments})


@login_required
@never_cache
def segment_create(request):
    company = _get_company(request)
    if request.method == 'POST' and company:
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip() or name.lower().replace(' ', '-')
        desc = request.POST.get('description', '')
        color = request.POST.get('color', '#6366f1')
        if name:
            CustomerSegment.objects.create(
                company=company, name=name, slug=slug, description=desc, color=color
            )
            messages.success(request, 'Segment created')
    return redirect('crm:segment_list')


@login_required
@never_cache
def segment_delete(request, pk):
    company = _get_company(request)
    if company:
        seg = get_object_or_404(CustomerSegment, pk=pk, company=company)
    else:
        seg = get_object_or_404(CustomerSegment, pk=pk)
    if request.method == 'POST':
        seg.delete()
        messages.success(request, 'Segment deleted')
    return redirect('crm:segment_list')


@login_required
@never_cache
def segment_assign(request, customer_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=customer_id, company=company)
    else:
        customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':
        segment_id = request.POST.get('segment_id')
        if segment_id:
            seg = get_object_or_404(CustomerSegment, pk=segment_id)
            CustomerSegmentAssignment.objects.get_or_create(
                customer=customer, segment=seg,
                defaults={'assigned_by': request.user}
            )
            messages.success(request, get_translation('segment_assigned', lang))

    return redirect(f'/crm/{customer.pk}/?tab=overview')


@login_required
@never_cache
def segment_remove(request, customer_id, assignment_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        assignment = get_object_or_404(
            CustomerSegmentAssignment.objects.select_related('customer'),
            pk=assignment_id, customer__company=company
        )
    else:
        assignment = get_object_or_404(CustomerSegmentAssignment, pk=assignment_id)
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, get_translation('segment_removed', lang))
    return redirect(f'/crm/{customer_id}/?tab=overview')


# ============================================================
# TAG MANAGEMENT
# ============================================================

@login_required
@never_cache
def tag_list(request):
    company = _get_company(request)
    if company:
        tags = CustomerTag.objects.filter(company=company).annotate(customer_count=Count('assignments__customer', distinct=True))
    else:
        tags = CustomerTag.objects.all().annotate(customer_count=Count('assignments__customer', distinct=True))
    return render(request, 'crm/tag_list.html', {'tags': tags})


@login_required
@never_cache
def tag_create(request):
    company = _get_company(request)
    if request.method == 'POST' and company:
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '#6b7280')
        if name:
            CustomerTag.objects.get_or_create(company=company, name=name, defaults={'color': color})
            messages.success(request, 'Tag created')
    return redirect('crm:tag_list')


@login_required
@never_cache
def tag_delete(request, pk):
    company = _get_company(request)
    if company:
        tag = get_object_or_404(CustomerTag, pk=pk, company=company)
    else:
        tag = get_object_or_404(CustomerTag, pk=pk)
    if request.method == 'POST':
        tag.delete()
        messages.success(request, 'Tag deleted')
    return redirect('crm:tag_list')


@login_required
@never_cache
def tag_assign(request, customer_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=customer_id, company=company)
    else:
        customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST':
        tag_id = request.POST.get('tag_id')
        if tag_id:
            tag = get_object_or_404(CustomerTag, pk=tag_id)
            CustomerTagAssignment.objects.get_or_create(
                customer=customer, tag=tag,
                defaults={'assigned_by': request.user}
            )
            messages.success(request, get_translation('tag_assigned', lang))

    return redirect(f'/crm/{customer.pk}/?tab=overview')


@login_required
@never_cache
def tag_remove(request, customer_id, assignment_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        assignment = get_object_or_404(
            CustomerTagAssignment.objects.select_related('customer'),
            pk=assignment_id, customer__company=company
        )
    else:
        assignment = get_object_or_404(CustomerTagAssignment, pk=assignment_id)
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, get_translation('tag_removed', lang))
    return redirect(f'/crm/{customer_id}/?tab=overview')


# ============================================================
# RFM ANALYSIS
# ============================================================

@login_required
@never_cache
def rfm_analyze(request):
    company = _get_company(request)
    lang = _lang(request)

    if company:
        customers = Customer.objects.filter(company=company, is_active=True)
    else:
        customers = Customer.objects.filter(is_active=True)

    today = timezone.now().date()
    recency_scores = {}
    frequency_scores = {}
    monetary_scores = {}

    for customer in customers:
        last_sale = Sale.objects.filter(
            customer=customer, status='completed'
        ).order_by('-created_at').first()

        if last_sale:
            days_since = (today - last_sale.created_at.date()).days
            if days_since <= 30:
                recency_scores[customer.pk] = 5
            elif days_since <= 60:
                recency_scores[customer.pk] = 4
            elif days_since <= 90:
                recency_scores[customer.pk] = 3
            elif days_since <= 180:
                recency_scores[customer.pk] = 2
            else:
                recency_scores[customer.pk] = 1
        else:
            recency_scores[customer.pk] = 1

        sale_count = Sale.objects.filter(customer=customer, status='completed').count()
        if sale_count >= 20:
            frequency_scores[customer.pk] = 5
        elif sale_count >= 10:
            frequency_scores[customer.pk] = 4
        elif sale_count >= 5:
            frequency_scores[customer.pk] = 3
        elif sale_count >= 2:
            frequency_scores[customer.pk] = 2
        else:
            frequency_scores[customer.pk] = 1

        total_val = Sale.objects.filter(
            customer=customer, status='completed'
        ).aggregate(t=Sum('total'))['t'] or 0
        if total_val >= 10000:
            monetary_scores[customer.pk] = 5
        elif total_val >= 5000:
            monetary_scores[customer.pk] = 4
        elif total_val >= 1000:
            monetary_scores[customer.pk] = 3
        elif total_val >= 100:
            monetary_scores[customer.pk] = 2
        else:
            monetary_scores[customer.pk] = 1

    SEGMENT_MAP = {
        (5, 5): 'Champions', (5, 4): 'Champions', (4, 5): 'Champions',
        (4, 4): 'Loyal Customers', (4, 3): 'Loyal Customers', (3, 5): 'Loyal Customers',
        (3, 4): 'Potential Loyalists', (3, 3): 'Potential Loyalists',
        (5, 1): 'New Customers', (5, 2): 'New Customers',
        (2, 4): 'At Risk', (2, 3): 'At Risk', (1, 4): 'At Risk', (1, 5): 'At Risk',
        (2, 2): 'Need Attention', (1, 3): 'Need Attention',
        (1, 2): 'Lost', (1, 1): 'Lost', (2, 1): 'Lost', (2, 5): 'Need Attention',
        (3, 2): 'Potential Loyalists', (3, 1): 'New Customers',
        (4, 1): 'New Customers', (4, 2): 'Potential Loyalists',
        (5, 3): 'Potential Loyalists',
    }

    customer_scores = []
    with transaction.atomic():
        for customer in customers:
            r = recency_scores.get(customer.pk, 1)
            f = frequency_scores.get(customer.pk, 1)
            m = monetary_scores.get(customer.pk, 1)
            segment_name = SEGMENT_MAP.get((r, f), 'New Customers')

            customer.rfm_recency = r
            customer.rfm_frequency = f
            customer.rfm_monetary = m
            customer.rfm_segment = segment_name
            customer.save(update_fields=['rfm_recency', 'rfm_frequency', 'rfm_monetary', 'rfm_segment'])

            customer_scores.append({
                'customer': customer,
                'recency': r,
                'frequency': f,
                'monetary': m,
                'total_score': r + f + m,
                'segment': segment_name,
            })

    customer_scores.sort(key=lambda x: x['total_score'], reverse=True)

    segment_groups = {}
    for cs in customer_scores:
        seg = cs['segment']
        if seg not in segment_groups:
            segment_groups[seg] = []
        segment_groups[seg].append(cs)

    context = {
        'customer_scores': customer_scores,
        'segment_groups': segment_groups,
        'total_analyzed': len(customer_scores),
    }
    return render(request, 'crm/rfm_analysis.html', context)


# ============================================================
# CUSTOMER EXPORT
# ============================================================

@login_required
@never_cache
def customer_export(request):
    company = _get_company(request)
    import csv
    from django.http import HttpResponse

    if company:
        customers = Customer.objects.filter(company=company)
    else:
        customers = Customer.objects.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customers_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Contact Person', 'Phone', 'Email', 'Telegram', 'Type',
        'Status', 'City', 'Region', 'Country', 'Tax ID', 'Credit Limit',
        'Payment Terms', 'Total Sales', 'Outstanding', 'Created',
    ])

    for c in customers:
        writer.writerow([
            c.name, c.contact_person, c.phone, c.email, c.telegram,
            c.get_customer_type_display(), c.get_customer_status_display(),
            c.city, c.region, c.country, c.tax_id, c.credit_limit,
            c.get_payment_terms_display(), c.total_sales, c.outstanding_balance,
            c.created_at.strftime('%d.%m.%Y'),
        ])

    return response


# ============================================================
# CUSTOMER QUICK ACTIONS
# ============================================================

@login_required
@never_cache
def customer_quick_action(request, pk):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=pk, company=company)
    else:
        customer = get_object_or_404(Customer, pk=pk)

    action = request.POST.get('action', '')
    if action == 'new_order':
        return redirect(f'/orders/create/?customer={customer.pk}')
    elif action == 'new_sale':
        return redirect(f'/sales/create/?customer={customer.pk}')
    elif action == 'record_payment':
        return redirect(f'/crm/{customer.pk}/?tab=payments')
    elif action == 'add_task':
        return redirect(f'/crm/{customer.pk}/?tab=tasks')
    elif action == 'add_note':
        return redirect(f'/crm/{customer.pk}/?tab=notes')

    return redirect(f'/crm/{customer.pk}/')


# ============================================================
# CUSTOMER DOCUMENTS
# ============================================================

@login_required
@never_cache
def document_upload(request, customer_id):
    company = _get_company(request)
    lang = _lang(request)
    if company:
        customer = get_object_or_404(Customer, pk=customer_id, company=company)
    else:
        customer = get_object_or_404(Customer, pk=customer_id)

    if request.method == 'POST' and request.FILES.get('file'):
        f = request.FILES['file']
        doc = CustomerDocument(
            company=company or customer.company,
            customer=customer,
            category=request.POST.get('category', 'other'),
            title=f.name,
            notes=request.POST.get('description', ''),
            created_by=request.user,
        )
        doc.file = f
        doc.save()
        messages.success(request, get_translation('document_uploaded', lang))

    return redirect(f'/crm/{customer.pk}/?tab=documents')


@login_required
@never_cache
def document_delete(request, pk):
    company = _get_company(request)
    if company:
        doc = get_object_or_404(CustomerDocument, pk=pk, company=company)
    else:
        doc = get_object_or_404(CustomerDocument, pk=pk)
    customer_id = doc.customer.pk
    if request.method == 'POST':
        doc.delete()
        messages.success(request, 'Document deleted')
    return redirect(f'/crm/{customer_id}/?tab=documents')
