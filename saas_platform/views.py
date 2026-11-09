import json
import logging
import csv
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator

from .models import (
    SubscriptionPlan, CompanySubscription, UsageLog, FeatureFlag,
    AuditLog, Permission, Role, UserRole, UserInvitation,
    CompanyMembership, HealthCheck, RateLimitRecord,
)
User = get_user_model()
logger = logging.getLogger('saas_platform')

TRYAL_DAYS = 14


def _get_company(request):
    return getattr(request, 'tenant', None)


def _require_platform_admin(user):
    return user.is_superuser and user.role == 'SUPER_ADMIN'


def _require_company_admin(user):
    return user.role in ('SUPER_ADMIN', 'COMPANY_ADMIN')


# ============================================================
# PLATFORM ADMIN DASHBOARD
# ============================================================
@login_required
def platform_dashboard(request):
    if not _require_platform_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    from users.models import Company

    companies = Company.objects.all()
    total_companies = companies.count()
    active_companies = companies.filter(is_active=True).count()
    total_users = User.objects.filter(is_active=True, is_deleted=False).count()

    from sales.models import Sale
    from finance.models import FinancialTransaction
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = float(Sale.objects.filter(
        created_at__gte=month_start, status__in=['confirmed', 'completed']
    ).aggregate(total=Sum('total'))['total'] or 0)

    recent_audits = AuditLog.objects.select_related('user', 'company').order_by('-created_at')[:15]
    health_checks = HealthCheck.objects.order_by('-checked_at')[:10]

    plan_stats = []
    for plan in SubscriptionPlan.objects.filter(is_active=True).order_by('display_order'):
        count = CompanySubscription.objects.filter(plan=plan, status__in=['trial', 'active']).count()
        plan_stats.append({'plan': plan, 'subscribers': count})

    context = {
        'total_companies': total_companies,
        'active_companies': active_companies,
        'total_users': total_users,
        'monthly_revenue': monthly_revenue,
        'recent_audits': recent_audits,
        'health_checks': health_checks,
        'plan_stats': plan_stats,
        'total_plans': SubscriptionPlan.objects.filter(is_active=True).count(),
    }
    return render(request, 'saas_platform/dashboard.html', context)


# ============================================================
# COMPANY MANAGEMENT
# ============================================================
@login_required
def company_list(request):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    from users.models import Company
    companies = Company.objects.annotate(
        employee_count=Count('employees', filter=Q(employees__is_active=True)),
    ).order_by('-created_at')

    search = request.GET.get('q', '')
    if search:
        companies = companies.filter(
            Q(company_name__icontains=search) | Q(email__icontains=search)
        )

    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        companies = companies.filter(is_active=True)
    elif status_filter == 'inactive':
        companies = companies.filter(is_active=False)

    paginator = Paginator(companies, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'companies': page_obj,
        'search': search,
        'status_filter': status_filter,
    }
    return render(request, 'saas_platform/company_list.html', context)


@login_required
def company_detail(request, company_id):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    from users.models import Company
    company = get_object_or_404(Company, pk=company_id)

    subscription = CompanySubscription.objects.filter(company=company).first()
    employees = User.objects.filter(company=company, is_active=True, is_deleted=False)
    roles = Role.objects.filter(Q(company=company) | Q(scope='platform'))
    usage_logs = UsageLog.objects.filter(company=company).order_by('-date')[:30]
    recent_audits = AuditLog.objects.filter(company=company).order_by('-created_at')[:20]
    flags = FeatureFlag.objects.filter(Q(company=company) | Q(scope='global')).order_by('key')

    context = {
        'company': company,
        'subscription': subscription,
        'employees': employees,
        'employee_count': employees.count(),
        'roles': roles,
        'usage_logs': usage_logs,
        'recent_audits': recent_audits,
        'flags': flags,
    }
    return render(request, 'saas_platform/company_detail.html', context)


@login_required
@csrf_protect
@require_POST
def company_toggle(request, company_id):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    from users.models import Company
    company = get_object_or_404(Company, pk=company_id)
    company.is_active = not company.is_active
    company.save(update_fields=['is_active'])

    AuditLog.log(
        action='update', company=company, user=request.user,
        resource_type='company', resource_id=str(company.pk),
        resource_name=company.company_name,
        description=f'Company {"activated" if company.is_active else "suspended"} by platform admin',
        request=request,
    )

    status = "activated" if company.is_active else "suspended"
    messages.success(request, f'Company {company.company_name} has been {status}.')
    return redirect('saas_platform:company_detail', company_id=company.pk)


# ============================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================
@login_required
def subscription_plans(request):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('display_order')
    context = {'plans': plans}
    return render(request, 'saas_platform/subscription_plans.html', context)


@login_required
@csrf_protect
@require_POST
def plan_create(request):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Plan name required.')
        return redirect('saas_platform:subscription_plans')

    plan = SubscriptionPlan.objects.create(
        name=name,
        slug=name.lower().replace(' ', '-'),
        description=request.POST.get('description', ''),
        price_monthly=Decimal(request.POST.get('price_monthly', 0)),
        price_yearly=Decimal(request.POST.get('price_yearly', 0)),
        max_users=int(request.POST.get('max_users', 5)),
        max_products=int(request.POST.get('max_products', 1000)),
        max_warehouses=int(request.POST.get('max_warehouses', 3)),
        max_orders_monthly=int(request.POST.get('max_orders_monthly', 500)),
        max_storage_mb=int(request.POST.get('max_storage_mb', 500)),
        max_api_calls_daily=int(request.POST.get('max_api_calls_daily', 1000)),
        max_ai_requests_monthly=int(request.POST.get('max_ai_requests_monthly', 100)),
        display_order=int(request.POST.get('display_order', 0)),
    )

    messages.success(request, f'Plan "{plan.name}" created.')
    return redirect('saas_platform:subscription_plans')


@login_required
@csrf_protect
@require_POST
def plan_update(request, plan_id):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    plan = get_object_or_404(SubscriptionPlan, pk=plan_id)
    plan.name = request.POST.get('name', plan.name)
    plan.description = request.POST.get('description', plan.description)
    plan.price_monthly = Decimal(request.POST.get('price_monthly', plan.price_monthly))
    plan.price_yearly = Decimal(request.POST.get('price_yearly', plan.price_yearly))
    plan.max_users = int(request.POST.get('max_users', plan.max_users))
    plan.max_products = int(request.POST.get('max_products', plan.max_products))
    plan.max_warehouses = int(request.POST.get('max_warehouses', plan.max_warehouses))
    plan.max_orders_monthly = int(request.POST.get('max_orders_monthly', plan.max_orders_monthly))
    plan.max_storage_mb = int(request.POST.get('max_storage_mb', plan.max_storage_mb))
    plan.max_api_calls_daily = int(request.POST.get('max_api_calls_daily', plan.max_api_calls_daily))
    plan.max_ai_requests_monthly = int(request.POST.get('max_ai_requests_monthly', plan.max_ai_requests_monthly))
    plan.display_order = int(request.POST.get('display_order', plan.display_order))
    plan.save()

    messages.success(request, f'Plan "{plan.name}" updated.')
    return redirect('saas_platform:subscription_plans')


@login_required
@csrf_protect
@require_POST
def company_set_plan(request, company_id):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    from users.models import Company
    company = get_object_or_404(Company, pk=company_id)
    plan_id = request.POST.get('plan_id')

    plan = get_object_or_404(SubscriptionPlan, pk=plan_id)

    sub, created = CompanySubscription.objects.get_or_create(
        company=company,
        defaults={'plan': plan, 'status': 'active', 'subscription_started': timezone.now()}
    )
    if not created:
        sub.plan = plan
        sub.status = 'active'
        sub.subscription_started = timezone.now()
        sub.save(update_fields=['plan', 'status', 'subscription_started', 'updated_at'])

    company.subscription_plan = plan.slug if hasattr(plan, 'slug') else 'professional'
    company.save(update_fields=['subscription_plan'])

    AuditLog.log(
        action='subscription_change', company=company, user=request.user,
        resource_type='subscription', resource_id=str(sub.pk),
        description=f'Plan changed to {plan.name}',
        request=request,
    )

    messages.success(request, f'Plan set to "{plan.name}" for {company.company_name}.')
    return redirect('saas_platform:company_detail', company_id=company.pk)


# ============================================================
# USER MANAGEMENT
# ============================================================
@login_required
def user_list(request):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    users = User.objects.filter(is_deleted=False).select_related('company').order_by('-created_at')

    search = request.GET.get('q', '')
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    paginator = Paginator(users, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'users_list': page_obj,
        'search': search,
    }
    return render(request, 'saas_platform/user_list.html', context)


# ============================================================
# ROLE & PERMISSION MANAGEMENT
# ============================================================
@login_required
def role_list(request):
    company = _get_company(request)
    if not company and not _require_platform_admin(request.user):
        return redirect('dashboard')

    if _require_platform_admin(request.user):
        roles = Role.objects.filter(scope='platform').order_by('name')
    else:
        roles = Role.objects.filter(
            Q(company=company) | Q(scope='platform', is_system=True)
        ).order_by('name')

    context = {'roles': roles, 'company': company}
    return render(request, 'saas_platform/role_list.html', context)


@login_required
@csrf_protect
@require_POST
def role_create(request):
    company = _get_company(request)
    if not _require_company_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Role name required.')
        return redirect('saas_platform:role_list')

    role = Role.objects.create(
        name=name,
        slug=name.lower().replace(' ', '-'),
        company=company,
        scope='company',
        description=request.POST.get('description', ''),
    )

    perm_ids = request.POST.getlist('permissions')
    if perm_ids:
        role.permissions.set(Permission.objects.filter(pk__in=perm_ids))

    AuditLog.log(
        action='role_change', company=company, user=request.user,
        resource_type='role', resource_id=str(role.pk),
        resource_name=role.name, description=f'Role "{name}" created',
        request=request,
    )

    messages.success(request, f'Role "{name}" created.')
    return redirect('saas_platform:role_list')


@login_required
@require_GET
def health_check_api(request):
    """Public-ish health check endpoint (no auth required for monitoring)."""
    results = {}

    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        results['database'] = 'healthy'
    except Exception as e:
        results['database'] = f'unhealthy: {str(e)}'

    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 5)
        val = cache.get('health_check')
        results['cache'] = 'healthy' if val == 'ok' else 'degraded'
    except Exception:
        results['cache'] = 'not_configured'

    results['application'] = 'healthy'
    results['timestamp'] = timezone.now().isoformat()

    all_healthy = all(v in ('healthy', 'not_configured') for k, v in results.items() if isinstance(v, str) and k != 'timestamp')
    status_code = 200 if all_healthy else 503

    for component, status in results.items():
        if isinstance(status, str) and status in ('healthy', 'degraded', 'unhealthy', 'not_configured'):
            HealthCheck.objects.create(
                component=component,
                status=status if status in ('healthy', 'degraded', 'unhealthy') else 'degraded',
                message=str(status),
            )

    return JsonResponse(results, status=status_code)


# ============================================================
# AUDIT LOG VIEWER
# ============================================================
@login_required
def audit_log_view(request):
    company = _get_company(request)
    if _require_platform_admin(request.user):
        logs = AuditLog.objects.select_related('user', 'company').order_by('-created_at')
    elif company:
        logs = AuditLog.objects.filter(company=company).select_related('user').order_by('-created_at')
    else:
        return redirect('dashboard')

    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = logs.filter(action=action_filter)

    user_filter = request.GET.get('user', '')
    if user_filter:
        logs = logs.filter(user_id=user_filter)

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    actions = AuditLog.ACTION_CHOICES
    context = {
        'page_obj': page_obj,
        'logs': page_obj,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'actions': actions,
    }
    return render(request, 'saas_platform/audit_log.html', context)


# ============================================================
# FEATURE FLAGS
# ============================================================
@login_required
def feature_flags(request):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    flags = FeatureFlag.objects.order_by('scope', 'key')
    context = {'flags': flags}
    return render(request, 'saas_platform/feature_flags.html', context)


@login_required
@csrf_protect
@require_POST
def flag_toggle(request, flag_id):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    flag = get_object_or_404(FeatureFlag, pk=flag_id)
    flag.enabled = not flag.enabled
    flag.save(update_fields=['enabled', 'updated_at'])

    AuditLog.log(
        action='update', user=request.user,
        resource_type='feature_flag', resource_id=str(flag.pk),
        resource_name=flag.key,
        description=f'Feature flag "{flag.key}" {"enabled" if flag.enabled else "disabled"}',
        request=request,
    )

    return redirect('saas_platform:feature_flags')


@login_required
@csrf_protect
@require_POST
def flag_create(request):
    if not _require_platform_admin(request.user):
        return redirect('dashboard')

    key = request.POST.get('key', '').strip().lower().replace(' ', '_')
    name = request.POST.get('name', '').strip()
    if not key or not name:
        messages.error(request, 'Key and name required.')
        return redirect('saas_platform:feature_flags')

    FeatureFlag.objects.create(
        key=key, name=name,
        description=request.POST.get('description', ''),
        scope=request.POST.get('scope', 'global'),
        enabled=request.POST.get('enabled') == 'on',
    )
    messages.success(request, f'Feature flag "{key}" created.')
    return redirect('saas_platform:feature_flags')


# ============================================================
# INVITATIONS
# ============================================================
@login_required
@csrf_protect
@require_POST
def invite_user(request):
    company = _get_company(request)
    if not company or not _require_company_admin(request.user):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    from users.models import Company
    company_obj = get_object_or_404(Company, pk=company.pk)

    email = request.POST.get('email', '').strip().lower()
    if not email:
        messages.error(request, 'Email required.')
        return redirect('users:employee_list')

    if User.objects.filter(email=email, is_active=True, is_deleted=False).exists():
        existing_membership = CompanyMembership.objects.filter(
            user__email=email, company=company, status='active'
        ).exists()
        if existing_membership:
            messages.warning(request, 'User already belongs to this company.')
            return redirect('users:employee_list')

    import secrets
    invitation = UserInvitation.objects.create(
        email=email,
        company=company_obj,
        invited_by=request.user,
        token=secrets.token_hex(32),
        role_legacy=request.POST.get('role', 'STAFF'),
        message=request.POST.get('message', ''),
    )

    AuditLog.log(
        action='create', company=company, user=request.user,
        resource_type='invitation', resource_id=str(invitation.pk),
        resource_name=email, description=f'Invitation sent to {email}',
        request=request,
    )

    messages.success(request, f'Invitation sent to {email}.')
    return redirect('users:employee_list')


# ============================================================
# EXPORT AUDIT LOG
# ============================================================
@login_required
def audit_export(request):
    company = _get_company(request)
    if _require_platform_admin(request.user):
        logs = AuditLog.objects.select_related('user', 'company').order_by('-created_at')
    elif company:
        logs = AuditLog.objects.filter(company=company).select_related('user').order_by('-created_at')
    else:
        return redirect('dashboard')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_log_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Action', 'User', 'Company', 'Resource Type', 'Resource ID', 'Description', 'IP Address'])
    for log in logs[:2000]:
        writer.writerow([
            log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.action,
            str(log.user) if log.user else '',
            str(log.company) if log.company else '',
            log.resource_type,
            log.resource_id,
            log.description,
            log.ip_address or '',
        ])

    return response
