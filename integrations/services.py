import hashlib
import hmac
import json
import logging
import secrets
import threading
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger('integrations')


DEFAULT_PROVIDERS = [
    {
        'name': 'Payme',
        'code': 'payme',
        'category': 'payment',
        'auth_type': 'api_key',
        'description': 'Payme payment gateway integration',
        'icon_class': 'bi-credit-card',
    },
    {
        'name': 'Click',
        'code': 'click',
        'category': 'payment',
        'auth_type': 'api_key',
        'description': 'Click payment system integration',
        'icon_class': 'bi-credit-card',
    },
    {
        'name': 'Stripe',
        'code': 'stripe',
        'category': 'payment',
        'auth_type': 'api_key',
        'description': 'Stripe international payment processing',
        'icon_class': 'bi-credit-card-2-front',
    },
    {
        'name': 'Uzum Bank',
        'code': 'uzum_bank',
        'category': 'payment',
        'auth_type': 'api_key',
        'description': 'Uzum Bank payment and settlement integration',
        'icon_class': 'bi-bank',
    },
    {
        'name': 'Bank Transfer',
        'code': 'bank_transfer',
        'category': 'bank',
        'auth_type': 'basic',
        'description': 'Manual and automated bank transfer processing',
        'icon_class': 'bi-bank2',
    },
    {
        'name': 'National Bank API',
        'code': 'national_bank',
        'category': 'bank',
        'auth_type': 'oauth2',
        'description': 'National Bank of Uzbekistan open API integration',
        'icon_class': 'bi-bank',
    },
    {
        'name': 'SMTP Email',
        'code': 'smtp_email',
        'category': 'email',
        'auth_type': 'basic',
        'description': 'SMTP email sending service',
        'icon_class': 'bi-envelope',
        'config_schema': {
            'type': 'object',
            'properties': {
                'host': {'type': 'string', 'title': 'SMTP Host', 'description': 'SMTP server hostname'},
                'port': {'type': 'integer', 'title': 'SMTP Port', 'default': 587},
                'from_address': {'type': 'string', 'title': 'From Address', 'description': 'Default sender email address'},
            },
            'required': ['host', 'port', 'from_address'],
        },
    },
    {
        'name': 'SendGrid',
        'code': 'sendgrid',
        'category': 'email',
        'auth_type': 'api_key',
        'description': 'SendGrid transactional and marketing email delivery',
        'icon_class': 'bi-envelope-check',
    },
    {
        'name': 'Telegram Bot',
        'code': 'telegram_bot',
        'category': 'messaging',
        'auth_type': 'api_key',
        'description': 'Telegram Bot API for notifications and messaging',
        'icon_class': 'bi-telegram',
        'config_schema': {
            'type': 'object',
            'properties': {
                'bot_token': {'type': 'string', 'title': 'Bot Token', 'description': 'Telegram bot token from @BotFather'},
            },
            'required': ['bot_token'],
        },
    },
    {
        'name': 'SMS Provider',
        'code': 'sms_provider',
        'category': 'sms',
        'auth_type': 'api_key',
        'description': 'SMS gateway for transactional and marketing messages',
        'icon_class': 'bi-phone',
    },
    {
        'name': 'Uzum Marketplace',
        'code': 'uzum_marketplace',
        'category': 'marketplace',
        'auth_type': 'api_key',
        'description': 'Uzum Marketplace seller API integration',
        'icon_class': 'bi-shop',
    },
    {
        'name': 'Wildberries',
        'code': 'wildberries',
        'category': 'marketplace',
        'auth_type': 'api_key',
        'description': 'Wildberries marketplace seller integration',
        'icon_class': 'bi-shop-window',
    },
    {
        'name': 'Ozon',
        'code': 'ozon',
        'category': 'marketplace',
        'auth_type': 'api_key',
        'description': 'Ozon marketplace seller API integration',
        'icon_class': 'bi-shop',
    },
    {
        'name': 'TezYetkazish',
        'code': 'tezyetkazish',
        'category': 'logistics',
        'auth_type': 'api_key',
        'description': 'TezYetkazish same-day delivery service',
        'icon_class': 'bi-truck',
    },
    {
        'name': 'Dostavista',
        'code': 'dostavista',
        'category': 'logistics',
        'auth_type': 'api_key',
        'description': 'Dostavista courier delivery service',
        'icon_class': 'bi-bicycle',
    },
    {
        'name': 'EDO Provider',
        'code': 'edo_provider',
        'category': 'documents',
        'auth_type': 'certificate',
        'description': 'Electronic document exchange (EDO) provider',
        'icon_class': 'bi-file-earmark-text',
    },
    {
        'name': '1C Integration',
        'code': 'onec',
        'category': 'erp',
        'auth_type': 'basic',
        'description': '1C:Enterprise ERP system data exchange',
        'icon_class': 'bi-database',
    },
    {
        'name': 'Dorival Marking',
        'code': 'dorival_marking',
        'category': 'marking',
        'auth_type': 'api_key',
        'description': 'Dorival product marking and labeling integration',
        'icon_class': 'bi-upc-scan',
    },
    {
        'name': 'MCHOT Marking',
        'code': 'mchot_marking',
        'category': 'marking',
        'auth_type': 'api_key',
        'description': 'MCHOT product marking system integration',
        'icon_class': 'bi-upc-scan',
    },
    {
        'name': 'Custom API',
        'code': 'custom_api',
        'category': 'custom',
        'auth_type': 'api_key',
        'description': 'Generic custom API integration with configurable endpoints',
        'icon_class': 'bi-gear',
    },
]


def seed_providers():
    from .models import IntegrationProvider
    created_count = 0
    updated_count = 0
    for data in DEFAULT_PROVIDERS:
        code = data['code']
        defaults = {k: v for k, v in data.items() if k != 'code'}
        obj, created = IntegrationProvider.objects.update_or_create(
            code=code,
            defaults=defaults,
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
    return {'created': created_count, 'updated': updated_count}


def get_dashboard_stats(company):
    from .models import (
        IntegrationConnection,
        SyncJob,
        WebhookEvent,
        IntegrationError,
        IntegrationLog,
    )

    connections = IntegrationConnection.objects.filter(company=company)

    status_counts = connections.values('status').annotate(count=Count('id'))
    status_map = {item['status']: item['count'] for item in status_counts}

    total = connections.count()
    connected = status_map.get('connected', 0)
    disconnected = status_map.get('disconnected', 0)
    error = status_map.get('error', 0)

    pending_syncs = SyncJob.objects.filter(
        connection__company=company,
        status='pending',
    ).count()

    failed_jobs = SyncJob.objects.filter(
        connection__company=company,
        status='failed',
    ).count()

    webhook_errors = WebhookEvent.objects.filter(
        endpoint__company=company,
        status='failed',
    ).count()

    recent_errors = list(
        IntegrationError.objects.filter(company=company, status='open')
        .order_by('-last_occurrence')[:10]
        .values('id', 'error_type', 'category', 'severity', 'message', 'last_occurrence')
    )

    recent_logs = list(
        IntegrationLog.objects.filter(company=company)
        .order_by('-created_at')[:20]
        .values('id', 'action', 'status', 'direction', 'created_at', 'duration_ms')
    )

    provider_category_stats = connections.values(
        'provider__category',
    ).annotate(
        total=Count('id'),
        connected_count=Count('id', filter=Q(status='connected')),
        error_count=Count('id', filter=Q(status='error')),
    ).order_by('provider__category')

    health_by_category = {}
    for row in provider_category_stats:
        cat = row['provider__category'] or 'other'
        health_by_category[cat] = {
            'total': row['total'],
            'connected': row['connected_count'],
            'error': row['error_count'],
        }

    return {
        'total_connections': total,
        'connected_count': connected,
        'disconnected_count': disconnected,
        'error_count': error,
        'pending_syncs': pending_syncs,
        'failed_jobs': failed_jobs,
        'webhook_errors': webhook_errors,
        'recent_errors': recent_errors,
        'recent_logs': recent_logs,
        'health_by_category': health_by_category,
    }


def get_integration_list(company, category_filter=None, search=None):
    from .models import IntegrationConnection

    queryset = IntegrationConnection.objects.filter(
        company=company,
    ).select_related('provider')

    if category_filter:
        queryset = queryset.filter(provider__category=category_filter)

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(provider__name__icontains=search)
        )

    return queryset


def test_connection(connection):
    from .adapters import AdapterRegistry

    adapter = AdapterRegistry.get_adapter(connection)
    if adapter is None:
        result = {'status': 'error', 'message': 'No adapter registered for this provider'}
    else:
        connection.status = 'testing'
        connection.save(update_fields=['status'])
        try:
            result = adapter.test_connection()
        except Exception as e:
            result = {'status': 'error', 'message': str(e)}

    connection.last_tested = timezone.now()
    connection.last_test_result = result

    status_value = result.get('status', 'error')
    status_map = {
        'connected': 'connected',
        'success': 'connected',
        'error': 'error',
        'disconnected': 'disconnected',
    }
    connection.status = status_map.get(status_value, 'error')

    if status_value in ('connected', 'success'):
        connection.health_status = 'healthy'
    else:
        connection.health_status = 'failing'
        connection.last_error = result.get('message', '')

    connection.save(update_fields=[
        'last_tested',
        'last_test_result',
        'status',
        'health_status',
        'last_error',
    ])
    return result


def run_sync_job(connection, job_type, triggered_by=None):
    from .models import SyncJob

    job = SyncJob.objects.create(
        connection=connection,
        job_type=job_type,
        status='pending',
        triggered_by=triggered_by,
    )

    def _execute(job_id):
        from .adapters import AdapterRegistry

        job_obj = SyncJob.objects.get(id=job_id)
        job_obj.status = 'running'
        job_obj.started_at = timezone.now()
        job_obj.save(update_fields=['status', 'started_at'])

        adapter = AdapterRegistry.get_adapter(job_obj.connection)
        if adapter is None:
            job_obj.status = 'failed'
            job_obj.error_summary = 'No adapter registered for this provider'
            job_obj.completed_at = timezone.now()
            if job_obj.started_at:
                job_obj.duration_seconds = int(
                    (job_obj.completed_at - job_obj.started_at).total_seconds()
                )
            job_obj.save(update_fields=[
                'status',
                'error_summary',
                'completed_at',
                'duration_seconds',
            ])
            return

        try:
            sync_method = getattr(adapter, job_obj.job_type, None)
            if sync_method and callable(sync_method):
                sync_result = sync_method()
                if isinstance(sync_result, dict):
                    job_obj.total_items = sync_result.get('total_items', 0)
                    job_obj.processed_items = sync_result.get('processed_items', 0)
                    job_obj.succeeded_items = sync_result.get('succeeded_items', 0)
                    job_obj.failed_items = sync_result.get('failed_items', 0)

            job_obj.status = 'completed'
            job_obj.completed_at = timezone.now()
            if job_obj.started_at:
                job_obj.duration_seconds = int(
                    (job_obj.completed_at - job_obj.started_at).total_seconds()
                )

            connection_obj = job_obj.connection
            connection_obj.last_successful_sync = timezone.now()
            connection_obj.save(update_fields=['last_successful_sync'])

        except Exception as e:
            job_obj.status = 'failed'
            job_obj.error_summary = str(e)[:1000]
            job_obj.completed_at = timezone.now()
            if job_obj.started_at:
                job_obj.duration_seconds = int(
                    (job_obj.completed_at - job_obj.started_at).total_seconds()
                )

        if job_obj.total_items > 0:
            job_obj.progress_percent = round(
                (job_obj.processed_items / job_obj.total_items) * 100, 2
            )

        job_obj.save()

    thread = threading.Thread(target=_execute, args=(job.id,), daemon=True)
    thread.start()

    return job


def dispatch_webhook(endpoint, event_type, payload):
    from .adapters import WebhookDispatcher

    dispatcher = WebhookDispatcher(endpoint)
    return dispatcher.dispatch(event_type, payload)


def verify_webhook_signature(payload, signature, secret):
    if not secret or not signature:
        return False
    return hmac.compare_digest(
        hmac.new(
            secret.encode('utf-8'),
            (json.dumps(payload, sort_keys=True, default=str) if isinstance(payload, dict) else payload).encode('utf-8'),
            hashlib.sha256,
        ).hexdigest(),
        signature.replace('sha256=', ''),
    )


def create_api_key(company, name, owner, scopes, expires_at=None):
    from .models import APIKey

    raw_key, key_hash, key_prefix = APIKey.generate_key()

    api_key = APIKey.objects.create(
        company=company,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        owner=owner,
        scopes=scopes,
        expires_at=expires_at,
    )

    return raw_key, api_key


def validate_api_key(raw_key):
    from .models import APIKey

    if not raw_key or not raw_key.startswith('sklat_'):
        return None

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    try:
        api_key = APIKey.objects.select_related('company').get(key_hash=key_hash)
    except APIKey.DoesNotExist:
        return None

    if not api_key.is_valid:
        return None

    api_key.last_used = timezone.now()
    api_key.usage_count += 1
    api_key.save(update_fields=['last_used', 'usage_count'])

    return api_key


def revoke_api_key(api_key_id, company):
    from .models import APIKey

    try:
        api_key = APIKey.objects.get(id=api_key_id, company=company)
    except APIKey.DoesNotExist:
        return False

    api_key.is_active = False
    api_key.save(update_fields=['is_active'])
    return True


def resolve_conflict(mapping_id, resolution):
    from .models import ExternalObjectMapping

    try:
        mapping = ExternalObjectMapping.objects.get(id=mapping_id)
    except ExternalObjectMapping.DoesNotExist:
        return None

    if resolution not in ('internal', 'external', 'manual'):
        return None

    mapping.source_of_truth = resolution
    mapping.has_conflict = False
    mapping.conflict_details = {}
    mapping.save(update_fields=['source_of_truth', 'has_conflict', 'conflict_details'])
    return mapping


def check_circuit_breakers(company):
    from .models import CircuitBreakerState, IntegrationConnection

    states = CircuitBreakerState.objects.filter(
        connection__company=company,
        state='open',
    ).select_related('connection')

    recovered = []
    for cb in states:
        if cb.opened_at:
            elapsed = (timezone.now() - cb.opened_at).total_seconds()
            if elapsed >= cb.recovery_timeout_seconds:
                cb.state = 'half_open'
                cb.success_count = 0
                cb.save(update_fields=['state', 'success_count'])

                cb.connection.health_status = 'unknown'
                cb.connection.circuit_open_until = None
                cb.connection.save(update_fields=['health_status', 'circuit_open_until'])

                recovered.append({
                    'connection_id': str(cb.connection_id),
                    'connection_name': cb.connection.name,
                    'previous_state': 'open',
                    'new_state': 'half_open',
                })

    return {
        'checked': states.count(),
        'recovered': recovered,
    }


def get_error_stats(company):
    from .models import IntegrationError

    errors = IntegrationError.objects.filter(company=company)

    by_category = errors.values('category').annotate(count=Count('id')).order_by('category')
    by_severity = errors.values('severity').annotate(count=Count('id')).order_by('severity')

    open_count = errors.filter(status='open').count()
    acknowledged_count = errors.filter(status='acknowledged').count()
    resolved_count = errors.filter(status='resolved').count()

    return {
        'by_category': {item['category']: item['count'] for item in by_category},
        'by_severity': {item['severity']: item['count'] for item in by_severity},
        'open_count': open_count,
        'acknowledged_count': acknowledged_count,
        'resolved_count': resolved_count,
        'total': errors.count(),
    }


def cleanup_old_logs(company, days=90):
    from .models import IntegrationLog, IntegrationError, WebhookEvent

    cutoff = timezone.now() - timedelta(days=days)

    deleted_logs = IntegrationLog.objects.filter(
        company=company,
        created_at__lt=cutoff,
    ).delete()

    deleted_errors = IntegrationError.objects.filter(
        company=company,
        status='resolved',
        resolved_at__lt=cutoff,
    ).delete()

    deleted_events = WebhookEvent.objects.filter(
        endpoint__company=company,
        status='processed',
        processed_at__lt=cutoff,
    ).delete()

    return {
        'logs_deleted': deleted_logs[0],
        'errors_deleted': deleted_errors[0],
        'events_deleted': deleted_events[0],
    }
