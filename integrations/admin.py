from django.contrib import admin
from .models import (
    IntegrationProvider, IntegrationConnection, IntegrationCredential,
    IntegrationConfig, OAuthConfig, SyncJob, WebhookEndpoint, WebhookEvent,
    IntegrationLog, IntegrationError, ExternalObjectMapping, APIKey,
    IntegrationEvent, CircuitBreakerState,
)


@admin.register(IntegrationProvider)
class IntegrationProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'auth_type', 'is_active']
    list_filter = ['category', 'auth_type', 'is_active']
    search_fields = ['name', 'code']


@admin.register(IntegrationConnection)
class IntegrationConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'company', 'status', 'environment', 'is_active', 'last_tested']
    list_filter = ['status', 'environment', 'is_active']
    search_fields = ['name']
    raw_id_fields = ['company', 'provider', 'created_by']


@admin.register(IntegrationCredential)
class IntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ['key_name', 'key_type', 'connection']
    list_filter = ['key_type']
    raw_id_fields = ['connection']


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ['job_type', 'connection', 'status', 'progress_percent', 'created_at']
    list_filter = ['status', 'job_type']
    raw_id_fields = ['connection']


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ['name', 'direction', 'status', 'is_active', 'failure_count']
    list_filter = ['direction', 'status']
    raw_id_fields = ['company', 'connection']


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'endpoint', 'status', 'direction', 'created_at']
    list_filter = ['status', 'direction']
    raw_id_fields = ['endpoint']


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'connection', 'direction', 'status', 'duration_ms', 'created_at']
    list_filter = ['status', 'direction']
    raw_id_fields = ['company', 'connection']
    readonly_fields = ['correlation_id']


@admin.register(IntegrationError)
class IntegrationErrorAdmin(admin.ModelAdmin):
    list_display = ['error_type', 'connection', 'category', 'severity', 'status', 'occurrence_count']
    list_filter = ['severity', 'status', 'category']
    raw_id_fields = ['company', 'connection']


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'key_prefix', 'company', 'is_active', 'expires_at', 'last_used']
    list_filter = ['is_active']
    raw_id_fields = ['company', 'owner']
    readonly_fields = ['key_hash', 'key_prefix']


@admin.register(IntegrationEvent)
class IntegrationEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'company', 'processed', 'created_at']
    list_filter = ['event_type', 'processed']
    raw_id_fields = ['company']


@admin.register(ExternalObjectMapping)
class ExternalObjectMappingAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'internal_id', 'external_id', 'connection', 'has_conflict', 'source_of_truth']
    list_filter = ['entity_type', 'has_conflict', 'source_of_truth']
    raw_id_fields = ['company', 'connection']
