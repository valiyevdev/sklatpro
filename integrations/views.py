from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from .models import (
    IntegrationConnection, IntegrationProvider, IntegrationLog, IntegrationError,
    SyncJob, WebhookEndpoint, WebhookEvent, APIKey,
    IntegrationCredential, IntegrationConfig, ExternalObjectMapping,
    CircuitBreakerState, IntegrationEvent,
)
from .adapters import AdapterRegistry



def get_company(request):
    if request.user.is_superuser:
        return getattr(request.user, 'company', None)
    return getattr(request.user, 'company', None)


@login_required
def integrations_dashboard(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        connections = IntegrationConnection.objects.filter(company=company)
        providers = IntegrationProvider.objects.filter(is_active=True)
        logs = IntegrationLog.objects.filter(company=company)
        errors = IntegrationError.objects.filter(company=company)
        sync_jobs = SyncJob.objects.filter(connection__company=company)
        webhook_endpoints = WebhookEndpoint.objects.filter(company=company)
        webhook_events = WebhookEvent.objects.filter(endpoint__company=company)

        total_connections = connections.count()
        connected = connections.filter(status='connected').count()
        disconnected = connections.filter(status='disconnected').count()
        error_connections = connections.filter(status='error').count()
        pending_syncs = sync_jobs.filter(status='pending').count()
        failed_jobs = sync_jobs.filter(status='failed').count()
        webhook_errors = webhook_endpoints.filter(failure_count__gt=0).count()

        category_stats = []
        for cat_code, cat_name in IntegrationProvider.CATEGORY_CHOICES:
            cat_providers = providers.filter(category=cat_code)
            cat_connections = connections.filter(provider__category=cat_code)
            cat_healthy = cat_connections.filter(health_status='healthy').count()
            cat_total = cat_connections.count()
            category_stats.append({
                'code': cat_code,
                'name': cat_name,
                'icon': _category_icon(cat_code),
                'total': cat_total,
                'healthy': cat_healthy,
                'status': 'healthy' if cat_total > 0 and cat_healthy == cat_total else ('degraded' if cat_healthy > 0 else 'failing' if cat_total > 0 else 'none'),
            })

        recent_errors = errors.exclude(status='resolved').order_by('-last_occurrence')[:10]
        recent_logs = logs.order_by('-created_at')[:15]

        context = {
            'connections': connections,
            'total_connections': total_connections,
            'connected': connected,
            'disconnected': disconnected,
            'error_connections': error_connections,
            'pending_syncs': pending_syncs,
            'failed_jobs': failed_jobs,
            'webhook_errors': webhook_errors,
            'category_stats': category_stats,
            'recent_errors': recent_errors,
            'recent_logs': recent_logs,
        }
        return render(request, 'integrations/dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        return render(request, 'integrations/dashboard.html', {})


def _category_icon(category):
    icons = {
        'payment': 'bi-credit-card',
        'bank': 'bi-bank',
        'messaging': 'bi-chat-dots',
        'email': 'bi-envelope',
        'sms': 'bi-phone',
        'ecommerce': 'bi-bag',
        'marketplace': 'bi-shop',
        'logistics': 'bi-truck',
        'documents': 'bi-file-earmark-text',
        'marking': 'bi-upc-scan',
        'accounting': 'bi-calculator',
        'erp': 'bi-database',
        'analytics': 'bi-bar-chart-line',
        'custom': 'bi-plug',
        'other': 'bi-gear',
    }
    return icons.get(category, 'bi-plug')


@login_required
def integration_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        connections = IntegrationConnection.objects.filter(company=company).select_related('provider')

        category = request.GET.get('category', '')
        status = request.GET.get('status', '')
        search = request.GET.get('q', '')

        if category:
            connections = connections.filter(provider__category=category)
        if status:
            connections = connections.filter(status=status)
        if search:
            connections = connections.filter(
                Q(name__icontains=search) |
                Q(provider__name__icontains=search) |
                Q(provider__code__icontains=search)
            )

        paginator = Paginator(connections, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'connections': page_obj,
            'category': category,
            'status': status,
            'search': search,
            'categories': IntegrationProvider.CATEGORY_CHOICES,
            'status_choices': IntegrationConnection.STATUS_CHOICES,
        }
        return render(request, 'integrations/list.html', context)
    except Exception as e:
        messages.error(request, f'Error loading connections: {str(e)}')
        return render(request, 'integrations/list.html', {'connections': []})


@login_required
def provider_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        providers = IntegrationProvider.objects.filter(is_active=True)
        search = request.GET.get('q', '')
        category = request.GET.get('category', '')

        if search:
            providers = providers.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        if category:
            providers = providers.filter(category=category)

        grouped = {}
        for provider in providers:
            cat = provider.category
            if cat not in grouped:
                grouped[cat] = {
                    'code': cat,
                    'name': dict(IntegrationProvider.CATEGORY_CHOICES).get(cat, cat),
                    'icon': _category_icon(cat),
                    'providers': [],
                }
            conn_count = IntegrationConnection.objects.filter(
                company=company, provider=provider
            ).count()
            grouped[cat]['providers'].append({
                'provider': provider,
                'connection_count': conn_count,
            })

        context = {
            'grouped': grouped,
            'search': search,
            'category': category,
            'categories': IntegrationProvider.CATEGORY_CHOICES,
        }
        return render(request, 'integrations/providers.html', context)
    except Exception as e:
        messages.error(request, f'Error loading providers: {str(e)}')
        return render(request, 'integrations/providers.html', {'grouped': {}})


@login_required
def connection_create(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        if request.method == 'POST':
            provider_id = request.POST.get('provider')
            provider = get_object_or_404(IntegrationProvider, pk=provider_id)

            connection = IntegrationConnection.objects.create(
                company=company,
                provider=provider,
                name=request.POST.get('name', ''),
                environment=request.POST.get('environment', 'production'),
                config=_parse_json_field(request.POST.get('config', '{}')),
                created_by=request.user,
            )

            credential_data = _extract_credentials(request.POST, provider.auth_type)
            for key_name, key_value in credential_data.items():
                if key_value:
                    IntegrationCredential.objects.create(
                        connection=connection,
                        key_name=key_name,
                        key_type=_key_type_for_auth(key_name, provider.auth_type),
                        value=key_value,
                    )

            IntegrationConfig.objects.create(connection=connection)

            messages.success(request, f'Connection "{connection.name}" created successfully.')
            return redirect('integrations:connection_detail', pk=connection.pk)

        provider_id = request.GET.get('provider', '')
        selected_provider = None
        if provider_id:
            selected_provider = get_object_or_404(IntegrationProvider, pk=provider_id)

        providers = IntegrationProvider.objects.filter(is_active=True)
        context = {
            'providers': providers,
            'selected_provider': selected_provider,
            'auth_types': IntegrationProvider.AUTH_TYPE_CHOICES,
            'environment_choices': IntegrationConnection.ENVIRONMENT_CHOICES,
            'credential_fields': _get_credential_fields(selected_provider.auth_type if selected_provider else 'api_key'),
        }
        return render(request, 'integrations/connection_create.html', context)
    except Exception as e:
        messages.error(request, f'Error creating connection: {str(e)}')
        return redirect('integrations:integration_list')


@login_required
def connection_detail(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        connection = get_object_or_404(
            IntegrationConnection.objects.select_related('provider'),
            pk=pk, company=company
        )
        credentials = connection.credentials.all()
        integration_config = getattr(connection, 'integration_config', None)
        oauth_config = getattr(connection, 'oauth_config', None)
        sync_jobs = connection.sync_jobs.all()[:20]
        recent_logs = connection.logs.all()[:20]
        webhooks = connection.webhook_endpoints.all()
        errors = connection.errors.exclude(status='resolved').order_by('-last_occurrence')[:10]
        object_mappings = connection.object_mappings.all()[:20]

        try:
            circuit_state = connection.circuit_state
        except CircuitBreakerState.DoesNotExist:
            circuit_state = None

        available_adapters = AdapterRegistry.get_all()

        context = {
            'connection': connection,
            'credentials': credentials,
            'integration_config': integration_config,
            'oauth_config': oauth_config,
            'sync_jobs': sync_jobs,
            'recent_logs': recent_logs,
            'webhooks': webhooks,
            'errors': errors,
            'object_mappings': object_mappings,
            'circuit_state': circuit_state,
            'available_adapters': available_adapters,
        }
        return render(request, 'integrations/connection_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading connection: {str(e)}')
        return redirect('integrations:integration_list')


@login_required
def connection_edit(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        connection = get_object_or_404(IntegrationConnection, pk=pk, company=company)

        if request.method == 'POST':
            connection.name = request.POST.get('name', connection.name)
            connection.environment = request.POST.get('environment', connection.environment)
            connection.config = _parse_json_field(request.POST.get('config', '{}'))
            connection.save()

            credential_data = _extract_credentials(request.POST, connection.provider.auth_type)
            for key_name, key_value in credential_data.items():
                if key_value:
                    IntegrationCredential.objects.update_or_create(
                        connection=connection,
                        key_name=key_name,
                        defaults={
                            'key_type': _key_type_for_auth(key_name, connection.provider.auth_type),
                            'value': key_value,
                        }
                    )

            if hasattr(connection, 'integration_config'):
                cfg = connection.integration_config
            else:
                cfg = IntegrationConfig(connection=connection)

            cfg.sync_enabled = request.POST.get('sync_enabled') == 'on'
            cfg.sync_interval_minutes = int(request.POST.get('sync_interval_minutes', 60))
            cfg.timeout_seconds = int(request.POST.get('timeout_seconds', 30))
            cfg.max_retries = int(request.POST.get('max_retries', 3))
            cfg.auto_retry_failed = request.POST.get('auto_retry_failed') == 'on'
            cfg.notify_on_error = request.POST.get('notify_on_error') == 'on'
            cfg.notify_on_disconnect = request.POST.get('notify_on_disconnect') == 'on'
            cfg.save()

            messages.success(request, f'Connection "{connection.name}" updated successfully.')
            return redirect('integrations:connection_detail', pk=connection.pk)

        credential_data = connection.masked_credentials
        context = {
            'connection': connection,
            'credential_data': credential_data,
            'environment_choices': IntegrationConnection.ENVIRONMENT_CHOICES,
        }
        return render(request, 'integrations/connection_edit.html', context)
    except Exception as e:
        messages.error(request, f'Error editing connection: {str(e)}')
        return redirect('integrations:integration_list')


@login_required
def connection_toggle(request, pk):
    company = get_company(request)
    if not company:
        return redirect('integrations:integration_list')

    try:
        connection = get_object_or_404(IntegrationConnection, pk=pk, company=company)
        connection.is_active = not connection.is_active
        if connection.is_active:
            connection.status = 'connected'
            messages.success(request, f'Connection "{connection.name}" activated.')
        else:
            connection.status = 'disconnected'
            messages.info(request, f'Connection "{connection.name}" deactivated.')
        connection.save(update_fields=['is_active', 'status'])
    except Exception as e:
        messages.error(request, f'Error toggling connection: {str(e)}')

    return redirect('integrations:connection_detail', pk=pk)


@login_required
def test_connection_view(request, pk):
    company = get_company(request)
    if not company:
        return JsonResponse({'status': 'error', 'message': 'No company found'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        connection = get_object_or_404(IntegrationConnection, pk=pk, company=company)
        adapter = AdapterRegistry.get_adapter(connection)

        if adapter is None:
            return JsonResponse({
                'status': 'error',
                'message': f'No adapter registered for provider "{connection.provider.code}"'
            })

        result = adapter.test_connection()

        connection.last_tested = timezone.now()
        connection.last_test_result = result
        if result.get('status') == 'connected':
            connection.status = 'connected'
            connection.health_status = 'healthy'
        else:
            connection.status = 'error'
            connection.health_status = 'failing'
            connection.last_error = result.get('message', 'Test failed')
        connection.save(update_fields=[
            'last_tested', 'last_test_result', 'status',
            'health_status', 'last_error'
        ])

        return JsonResponse(result)
    except IntegrationConnection.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Connection not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def sync_jobs_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        jobs = SyncJob.objects.filter(connection__company=company).select_related('connection', 'connection__provider')

        connection_id = request.GET.get('connection', '')
        status_filter = request.GET.get('status', '')
        job_type = request.GET.get('type', '')

        if connection_id:
            jobs = jobs.filter(connection_id=connection_id)
        if status_filter:
            jobs = jobs.filter(status=status_filter)
        if job_type:
            jobs = jobs.filter(job_type=job_type)

        paginator = Paginator(jobs, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        connections = IntegrationConnection.objects.filter(company=company)

        context = {
            'page_obj': page_obj,
            'jobs': page_obj,
            'connection_id': connection_id,
            'status_filter': status_filter,
            'job_type': job_type,
            'connections': connections,
            'status_choices': SyncJob.STATUS_CHOICES,
            'job_type_choices': SyncJob.TYPE_CHOICES,
        }
        return render(request, 'integrations/sync_jobs.html', context)
    except Exception as e:
        messages.error(request, f'Error loading sync jobs: {str(e)}')
        return render(request, 'integrations/sync_jobs.html', {'jobs': []})


@login_required
def sync_job_detail(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        job = get_object_or_404(
            SyncJob.objects.select_related('connection', 'connection__provider', 'triggered_by'),
            pk=pk, connection__company=company
        )
        logs = IntegrationLog.objects.filter(
            company=company, connection=job.connection,
            created_at__gte=job.created_at
        ).order_by('-created_at')[:20]

        context = {
            'job': job,
            'logs': logs,
        }
        return render(request, 'integrations/sync_job_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading sync job: {str(e)}')
        return redirect('integrations:sync_jobs')


@login_required
def sync_job_retry(request, pk):
    company = get_company(request)
    if not company:
        return redirect('integrations:sync_jobs')

    try:
        job = get_object_or_404(SyncJob, pk=pk, connection__company=company)

        if not job.can_retry:
            messages.error(request, 'This job cannot be retried.')
            return redirect('integrations:sync_job_detail', pk=pk)

        if request.method == 'POST':
            job.status = 'pending'
            job.retry_count += 1
            job.error_summary = ''
            job.error_details = {}
            job.started_at = None
            job.completed_at = None
            job.duration_seconds = None
            job.save(update_fields=[
                'status', 'retry_count', 'error_summary',
                'error_details', 'started_at', 'completed_at', 'duration_seconds'
            ])
            messages.success(request, f'Sync job "{job.get_job_type_display()}" queued for retry.')

        return redirect('integrations:sync_job_detail', pk=pk)
    except Exception as e:
        messages.error(request, f'Error retrying sync job: {str(e)}')
        return redirect('integrations:sync_jobs')


@login_required
def sync_job_cancel(request, pk):
    company = get_company(request)
    if not company:
        return redirect('integrations:sync_jobs')

    try:
        job = get_object_or_404(SyncJob, pk=pk, connection__company=company)

        if request.method == 'POST':
            if job.status in ('pending', 'running', 'retrying'):
                job.status = 'cancelled'
                job.completed_at = timezone.now()
                if job.started_at:
                    job.duration_seconds = int((job.completed_at - job.started_at).total_seconds())
                job.save(update_fields=['status', 'completed_at', 'duration_seconds'])
                messages.success(request, f'Sync job "{job.get_job_type_display()}" cancelled.')
            else:
                messages.info(request, 'This job cannot be cancelled in its current state.')

        return redirect('integrations:sync_job_detail', pk=pk)
    except Exception as e:
        messages.error(request, f'Error cancelling sync job: {str(e)}')
        return redirect('integrations:sync_jobs')


@login_required
def webhook_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        webhooks = WebhookEndpoint.objects.filter(company=company).select_related('connection')
        direction = request.GET.get('direction', '')
        status = request.GET.get('status', '')
        search = request.GET.get('q', '')

        if direction:
            webhooks = webhooks.filter(direction=direction)
        if status:
            webhooks = webhooks.filter(status=status)
        if search:
            webhooks = webhooks.filter(Q(name__icontains=search) | Q(url__icontains=search))

        paginator = Paginator(webhooks, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'webhooks': page_obj,
            'direction': direction,
            'status': status,
            'search': search,
            'direction_choices': WebhookEndpoint.DIRECTION_CHOICES,
            'status_choices': WebhookEndpoint.STATUS_CHOICES,
        }
        return render(request, 'integrations/webhook_list.html', context)
    except Exception:
        return render(request, 'integrations/webhook_list.html', {'webhooks': []})


@login_required
def webhook_create(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        if request.method == 'POST':
            connection_id = request.POST.get('connection')
            connection = None
            if connection_id:
                connection = get_object_or_404(IntegrationConnection, pk=connection_id, company=company)

            webhook = WebhookEndpoint.objects.create(
                company=company,
                connection=connection,
                name=request.POST.get('name', ''),
                url=request.POST.get('url', ''),
                direction=request.POST.get('direction', 'outgoing'),
                event_types=_parse_json_field(request.POST.get('event_types', '[]')),
                headers=_parse_json_field(request.POST.get('headers', '{}')),
                is_active=request.POST.get('is_active') == 'on',
            )
            messages.success(request, f'Webhook "{webhook.name}" created successfully.')
            return redirect('integrations:webhook_detail', pk=webhook.pk)

        connections = IntegrationConnection.objects.filter(company=company)
        context = {
            'connections': connections,
            'direction_choices': WebhookEndpoint.DIRECTION_CHOICES,
        }
        return render(request, 'integrations/webhook_create.html', context)
    except Exception as e:
        messages.error(request, f'Error creating webhook: {str(e)}')
        return redirect('integrations:webhook_list')


@login_required
def webhook_detail(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        webhook = get_object_or_404(
            WebhookEndpoint.objects.select_related('connection'),
            pk=pk, company=company
        )
        recent_events = webhook.events.all()[:50]

        paginator = Paginator(recent_events, 20)
        page_number = request.GET.get('page')
        events_page = paginator.get_page(page_number)

        context = {
            'webhook': webhook,
            'events': events_page,
            'page_obj': events_page,
        }
        return render(request, 'integrations/webhook_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading webhook: {str(e)}')
        return redirect('integrations:webhook_list')


@login_required
def webhook_toggle(request, pk):
    company = get_company(request)
    if not company:
        return redirect('integrations:webhook_list')

    try:
        webhook = get_object_or_404(WebhookEndpoint, pk=pk, company=company)
        webhook.is_active = not webhook.is_active
        if webhook.is_active:
            webhook.status = 'active'
            messages.success(request, f'Webhook "{webhook.name}" activated.')
        else:
            webhook.status = 'inactive'
            messages.info(request, f'Webhook "{webhook.name}" deactivated.')
        webhook.save(update_fields=['is_active', 'status'])
    except Exception as e:
        messages.error(request, f'Error toggling webhook: {str(e)}')

    return redirect('integrations:webhook_detail', pk=pk)


@login_required
def webhook_events(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        events = WebhookEvent.objects.filter(endpoint__company=company).select_related('endpoint')

        endpoint_id = request.GET.get('endpoint', '')
        status = request.GET.get('status', '')
        direction = request.GET.get('direction', '')
        event_type = request.GET.get('event_type', '')

        if endpoint_id:
            events = events.filter(endpoint_id=endpoint_id)
        if status:
            events = events.filter(status=status)
        if direction:
            events = events.filter(direction=direction)
        if event_type:
            events = events.filter(event_type=event_type)

        paginator = Paginator(events, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        endpoints = WebhookEndpoint.objects.filter(company=company)

        context = {
            'page_obj': page_obj,
            'events': page_obj,
            'endpoint_id': endpoint_id,
            'status': status,
            'direction': direction,
            'event_type': event_type,
            'endpoints': endpoints,
            'status_choices': WebhookEvent.STATUS_CHOICES,
            'direction_choices': WebhookEndpoint.DIRECTION_CHOICES,
        }
        return render(request, 'integrations/webhook_events.html', context)
    except Exception as e:
        messages.error(request, f'Error loading webhook events: {str(e)}')
        return render(request, 'integrations/webhook_events.html', {'events': []})


@login_required
def api_key_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        api_keys = APIKey.objects.filter(company=company)

        context = {
            'api_keys': api_keys,
        }
        return render(request, 'integrations/api_keys.html', context)
    except Exception as e:
        messages.error(request, f'Error loading API keys: {str(e)}')
        return render(request, 'integrations/api_keys.html', {'api_keys': []})


@login_required
def api_key_create(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        if request.method == 'POST':
            raw_key, key_hash, key_prefix = APIKey.generate_key()

            api_key = APIKey.objects.create(
                company=company,
                name=request.POST.get('name', ''),
                key_hash=key_hash,
                key_prefix=key_prefix,
                owner=request.user,
                scopes=_parse_json_field(request.POST.get('scopes', '[]')),
                expires_at=_parse_datetime(request.POST.get('expires_at')),
                rate_limit_per_minute=int(request.POST.get('rate_limit_per_minute', 60)),
            )

            messages.success(request, 'API key created successfully.')
            context = {
                'api_key': api_key,
                'raw_key': raw_key,
                'show_key': True,
            }
            return render(request, 'integrations/api_key_create.html', context)

        context = {
            'scope_choices': APIKey.SCOPE_CHOICES,
        }
        return render(request, 'integrations/api_key_create.html', context)
    except Exception as e:
        messages.error(request, f'Error creating API key: {str(e)}')
        return redirect('integrations:api_key_list')


@login_required
def api_key_revoke(request, pk):
    company = get_company(request)
    if not company:
        return redirect('integrations:api_key_list')

    try:
        api_key = get_object_or_404(APIKey, pk=pk, company=company)

        if request.method == 'POST':
            api_key.is_active = False
            api_key.save(update_fields=['is_active'])
            messages.success(request, f'API key "{api_key.name}" has been revoked.')

        return redirect('integrations:api_key_list')
    except Exception as e:
        messages.error(request, f'Error revoking API key: {str(e)}')
        return redirect('integrations:api_key_list')


@login_required
def integration_logs(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        logs = IntegrationLog.objects.filter(company=company).select_related('connection')

        connection_id = request.GET.get('connection', '')
        status = request.GET.get('status', '')
        direction = request.GET.get('direction', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        if connection_id:
            logs = logs.filter(connection_id=connection_id)
        if status:
            logs = logs.filter(status=status)
        if direction:
            logs = logs.filter(direction=direction)
        if date_from:
            try:
                logs = logs.filter(created_at__date__gte=date_from)
            except (ValueError, TypeError):
                pass
        if date_to:
            try:
                logs = logs.filter(created_at__date__lte=date_to)
            except (ValueError, TypeError):
                pass

        paginator = Paginator(logs, 30)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        connections = IntegrationConnection.objects.filter(company=company)

        context = {
            'page_obj': page_obj,
            'logs': page_obj,
            'connection_id': connection_id,
            'status': status,
            'direction': direction,
            'date_from': date_from,
            'date_to': date_to,
            'connections': connections,
            'status_choices': IntegrationLog.STATUS_CHOICES,
            'direction_choices': IntegrationLog.DIRECTION_CHOICES,
        }
        return render(request, 'integrations/logs.html', context)
    except Exception as e:
        messages.error(request, f'Error loading logs: {str(e)}')
        return render(request, 'integrations/logs.html', {'logs': []})


@login_required
def integration_errors(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        errors = IntegrationError.objects.filter(company=company).select_related('connection', 'connection__provider')

        status = request.GET.get('status', '')
        severity = request.GET.get('severity', '')
        category = request.GET.get('category', '')

        if status:
            errors = errors.filter(status=status)
        if severity:
            errors = errors.filter(severity=severity)
        if category:
            errors = errors.filter(category=category)

        if request.method == 'POST':
            action = request.POST.get('action')
            error_id = request.POST.get('error_id')
            error = get_object_or_404(IntegrationError, pk=error_id, company=company)

            if action == 'acknowledge':
                error.status = 'acknowledged'
                error.save(update_fields=['status'])
                messages.success(request, 'Error acknowledged.')
            elif action == 'resolve':
                error.status = 'resolved'
                error.resolved_at = timezone.now()
                error.resolution_notes = request.POST.get('resolution_notes', '')
                error.save(update_fields=['status', 'resolved_at', 'resolution_notes'])
                messages.success(request, 'Error resolved.')
            return redirect('integrations:errors')

        paginator = Paginator(errors, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'errors': page_obj,
            'status': status,
            'severity': severity,
            'category': category,
            'status_choices': IntegrationError.STATUS_CHOICES,
            'severity_choices': IntegrationError.SEVERITY_CHOICES,
            'category_choices': IntegrationLog.ERROR_CATEGORY_CHOICES,
        }
        return render(request, 'integrations/errors.html', context)
    except Exception as e:
        messages.error(request, f'Error loading errors: {str(e)}')
        return render(request, 'integrations/errors.html', {'errors': []})


@login_required
def object_mappings(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        mappings = ExternalObjectMapping.objects.filter(
            company=company
        ).select_related('connection', 'connection__provider')

        entity_type = request.GET.get('entity_type', '')
        conflict = request.GET.get('conflict', '')

        if entity_type:
            mappings = mappings.filter(entity_type=entity_type)
        if conflict == 'true':
            mappings = mappings.filter(has_conflict=True)
        elif conflict == 'false':
            mappings = mappings.filter(has_conflict=False)

        if request.method == 'POST':
            action = request.POST.get('action')
            mapping_id = request.POST.get('mapping_id')
            mapping = get_object_or_404(ExternalObjectMapping, pk=mapping_id, company=company)

            if action == 'resolve_internal':
                mapping.source_of_truth = 'internal'
                mapping.has_conflict = False
                mapping.conflict_details = {}
                mapping.save(update_fields=['source_of_truth', 'has_conflict', 'conflict_details'])
                messages.success(request, 'Conflict resolved: Internal source selected.')
            elif action == 'resolve_external':
                mapping.source_of_truth = 'external'
                mapping.has_conflict = False
                mapping.conflict_details = {}
                mapping.save(update_fields=['source_of_truth', 'has_conflict', 'conflict_details'])
                messages.success(request, 'Conflict resolved: External source selected.')
            elif action == 'resolve_manual':
                mapping.source_of_truth = 'manual'
                mapping.has_conflict = False
                mapping.save(update_fields=['source_of_truth', 'has_conflict'])
                messages.success(request, 'Marked for manual review.')
            return redirect('integrations:object_mappings')

        paginator = Paginator(mappings, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'mappings': page_obj,
            'entity_type': entity_type,
            'conflict': conflict,
            'entity_choices': ExternalObjectMapping.ENTITY_CHOICES,
            'conflict_count': ExternalObjectMapping.objects.filter(company=company, has_conflict=True).count(),
        }
        return render(request, 'integrations/object_mappings.html', context)
    except Exception as e:
        messages.error(request, f'Error loading object mappings: {str(e)}')
        return render(request, 'integrations/object_mappings.html', {'mappings': []})


@login_required
def circuit_breaker_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        states = CircuitBreakerState.objects.filter(
            connection__company=company
        ).select_related('connection', 'connection__provider').order_by('-failure_count')

        state_filter = request.GET.get('state', '')
        if state_filter:
            states = states.filter(state=state_filter)

        paginator = Paginator(states, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'states': page_obj,
            'state_filter': state_filter,
            'state_choices': CircuitBreakerState.STATE_CHOICES,
        }
        return render(request, 'integrations/circuit_breakers.html', context)
    except Exception as e:
        messages.error(request, f'Error loading circuit breakers: {str(e)}')
        return render(request, 'integrations/circuit_breakers.html', {'states': []})


@login_required
def integration_events(request):
    company = get_company(request)
    if not company:
        return render(request, 'integrations/no_company.html')

    try:
        events = IntegrationEvent.objects.filter(company=company)

        event_type = request.GET.get('event_type', '')
        processed = request.GET.get('processed', '')

        if event_type:
            events = events.filter(event_type=event_type)
        if processed == 'true':
            events = events.filter(processed=True)
        elif processed == 'false':
            events = events.filter(processed=False)

        paginator = Paginator(events, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'events': page_obj,
            'event_type': event_type,
            'processed': processed,
            'event_type_choices': IntegrationEvent.EVENT_TYPE_CHOICES,
        }
        return render(request, 'integrations/events.html', context)
    except Exception as e:
        messages.error(request, f'Error loading events: {str(e)}')
        return render(request, 'integrations/events.html', {'events': []})


def _parse_json_field(value):
    import json
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_datetime(value):
    if not value:
        return None
    try:
        return timezone.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _extract_credentials(post_data, auth_type):
    credential_map = {
        'api_key': [('api_key', 'API Key'), ('api_secret', 'API Secret')],
        'oauth2': [('client_id', 'Client ID'), ('client_secret', 'Client Secret')],
        'basic': [('username', 'Username'), ('password', 'Password')],
        'bearer': [('access_token', 'Access Token')],
        'certificate': [('certificate', 'Certificate'), ('private_key', 'Private Key')],
        'webhook_secret': [('webhook_secret', 'Webhook Secret')],
        'custom': [('api_key', 'API Key'), ('api_secret', 'API Secret'), ('access_token', 'Access Token')],
    }
    fields = credential_map.get(auth_type, credential_map['api_key'])
    result = {}
    for key_name, _ in fields:
        value = post_data.get(f'cred_{key_name}', '').strip()
        if value and not value.startswith('****'):
            result[key_name] = value
    return result


def _key_type_for_auth(key_name, auth_type):
    key_type_map = {
        'api_key': 'api_key',
        'api_secret': 'api_secret',
        'client_id': 'client_id',
        'client_secret': 'client_secret',
        'username': 'username',
        'password': 'password',
        'access_token': 'access_token',
        'certificate': 'certificate',
        'private_key': 'private_key',
        'webhook_secret': 'webhook_secret',
    }
    return key_type_map.get(key_name, 'api_key')


def _get_credential_fields(auth_type):
    fields = {
        'api_key': [
            {'name': 'api_key', 'label': 'API Key', 'type': 'password'},
            {'name': 'api_secret', 'label': 'API Secret', 'type': 'password'},
        ],
        'oauth2': [
            {'name': 'client_id', 'label': 'Client ID', 'type': 'text'},
            {'name': 'client_secret', 'label': 'Client Secret', 'type': 'password'},
        ],
        'basic': [
            {'name': 'username', 'label': 'Username', 'type': 'text'},
            {'name': 'password', 'label': 'Password', 'type': 'password'},
        ],
        'bearer': [
            {'name': 'access_token', 'label': 'Access Token', 'type': 'password'},
        ],
        'certificate': [
            {'name': 'certificate', 'label': 'Certificate', 'type': 'textarea'},
            {'name': 'private_key', 'label': 'Private Key', 'type': 'textarea'},
        ],
        'webhook_secret': [
            {'name': 'webhook_secret', 'label': 'Webhook Secret', 'type': 'password'},
        ],
        'custom': [
            {'name': 'api_key', 'label': 'API Key', 'type': 'password'},
            {'name': 'api_secret', 'label': 'API Secret', 'type': 'password'},
            {'name': 'access_token', 'label': 'Access Token', 'type': 'password'},
        ],
    }
    return fields.get(auth_type, fields['api_key'])
