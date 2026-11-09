import uuid
import hashlib
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify


class IntegrationProvider(models.Model):
    CATEGORY_CHOICES = [
        ('payment', 'Payment'),
        ('bank', 'Bank'),
        ('messaging', 'Messaging'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('ecommerce', 'E-Commerce'),
        ('marketplace', 'Marketplace'),
        ('logistics', 'Logistics'),
        ('documents', 'Documents / EDO'),
        ('marking', 'Product Marking'),
        ('accounting', 'Accounting'),
        ('erp', 'ERP'),
        ('analytics', 'Analytics'),
        ('custom', 'Custom API'),
        ('other', 'Other'),
    ]
    AUTH_TYPE_CHOICES = [
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth 2.0'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('certificate', 'Certificate'),
        ('webhook_secret', 'Webhook Secret'),
        ('custom', 'Custom'),
    ]
    HEALTH_CHOICES = [
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('failing', 'Failing'),
        ('circuit_open', 'Circuit Open'),
        ('unknown', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=50, unique=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    auth_type = models.CharField(max_length=30, choices=AUTH_TYPE_CHOICES, default='api_key')
    config_schema = models.JSONField(default=dict, blank=True,
        help_text='JSON schema defining required configuration fields')
    health_status = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='unknown')
    documentation_url = models.URLField(blank=True)
    icon_class = models.CharField(max_length=50, blank=True, default='bi-plug')
    is_active = models.BooleanField(default=True)
    version = models.CharField(max_length=20, blank=True, default='1.0')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class IntegrationConnection(models.Model):
    ENVIRONMENT_CHOICES = [
        ('sandbox', 'Sandbox'),
        ('test', 'Test'),
        ('production', 'Production'),
    ]
    STATUS_CHOICES = [
        ('not_configured', 'Not Configured'),
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
        ('suspended', 'Suspended'),
        ('testing', 'Testing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='integration_connections')
    provider = models.ForeignKey(IntegrationProvider, on_delete=models.CASCADE, related_name='connections')
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_configured')
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default='production')
    config = models.JSONField(default=dict, blank=True,
        help_text='Non-secret configuration values')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_tested = models.DateTimeField(null=True, blank=True)
    last_test_result = models.JSONField(default=dict, blank=True)
    last_successful_sync = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    health_status = models.CharField(max_length=20, default='unknown')
    failure_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    circuit_open_until = models.DateTimeField(null=True, blank=True)
    rate_limit_remaining = models.PositiveIntegerField(null=True, blank=True)
    rate_limit_reset = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['company', 'provider', 'name']

    def __str__(self):
        return f"{self.name} ({self.provider.name})"

    @property
    def is_circuit_open(self):
        if self.circuit_open_until and self.circuit_open_until > timezone.now():
            return True
        return False

    @property
    def masked_credentials(self):
        creds = self.credentials.all()
        result = {}
        for c in creds:
            val = c.value
            if len(val) > 8:
                result[c.key_name] = val[:4] + '*' * (len(val) - 8) + val[-4:]
            else:
                result[c.key_name] = '****'
        return result


class IntegrationCredential(models.Model):
    KEY_TYPE_CHOICES = [
        ('api_key', 'API Key'),
        ('api_secret', 'API Secret'),
        ('access_token', 'Access Token'),
        ('refresh_token', 'Refresh Token'),
        ('username', 'Username'),
        ('password', 'Password'),
        ('certificate', 'Certificate'),
        ('private_key', 'Private Key'),
        ('webhook_secret', 'Webhook Secret'),
        ('client_id', 'Client ID'),
        ('client_secret', 'Client Secret'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE, related_name='credentials')
    key_name = models.CharField(max_length=100)
    key_type = models.CharField(max_length=30, choices=KEY_TYPE_CHOICES)
    value = models.TextField()
    is_encrypted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key_name']
        unique_together = ['connection', 'key_name']

    def __str__(self):
        return f"{self.key_name} ({self.get_key_type_display()})"

    @property
    def masked_value(self):
        if len(self.value) > 8:
            return self.value[:4] + '*' * (len(self.value) - 8) + self.value[-4:]
        return '****'


class IntegrationConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.OneToOneField(IntegrationConnection, on_delete=models.CASCADE, related_name='integration_config')
    webhook_url = models.URLField(blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)
    callback_url = models.URLField(blank=True)
    sync_enabled = models.BooleanField(default=False)
    sync_interval_minutes = models.PositiveIntegerField(default=60)
    sync_entities = models.JSONField(default=list, blank=True,
        help_text='List of entity types to sync: products, stock, prices, orders')
    timeout_seconds = models.PositiveIntegerField(default=30)
    max_retries = models.PositiveIntegerField(default=3)
    retry_delay_seconds = models.PositiveIntegerField(default=60)
    rate_limit_per_minute = models.PositiveIntegerField(null=True, blank=True)
    custom_headers = models.JSONField(default=dict, blank=True)
    custom_params = models.JSONField(default=dict, blank=True)
    log_retention_days = models.PositiveIntegerField(default=90)
    auto_retry_failed = models.BooleanField(default=True)
    notify_on_error = models.BooleanField(default=True)
    notify_on_disconnect = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Config for {self.connection.name}"


class OAuthConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.OneToOneField(IntegrationConnection, on_delete=models.CASCADE, related_name='oauth_config')
    authorization_url = models.URLField(blank=True)
    token_url = models.URLField(blank=True)
    client_id = models.CharField(max_length=255, blank=True)
    client_secret = models.CharField(max_length=255, blank=True)
    redirect_uri = models.URLField(blank=True)
    scopes = models.JSONField(default=list, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expiry = models.DateTimeField(null=True, blank=True)
    state = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_token_expired(self):
        if not self.token_expiry:
            return True
        return self.token_expiry <= timezone.now()

    @property
    def masked_client_secret(self):
        if len(self.client_secret) > 8:
            return self.client_secret[:4] + '*' * (len(self.client_secret) - 8) + self.client_secret[-4:]
        return '****'


class SyncJob(models.Model):
    TYPE_CHOICES = [
        ('product_sync', 'Product Sync'),
        ('stock_sync', 'Stock Sync'),
        ('price_sync', 'Price Sync'),
        ('order_import', 'Order Import'),
        ('order_export', 'Order Export'),
        ('customer_sync', 'Customer Sync'),
        ('document_send', 'Document Send'),
        ('notification_send', 'Notification Send'),
        ('shipment_update', 'Shipment Update'),
        ('payment_check', 'Payment Check'),
        ('balance_check', 'Balance Check'),
        ('full_sync', 'Full Sync'),
        ('custom', 'Custom'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('retrying', 'Retrying'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE, related_name='sync_jobs')
    job_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    direction = models.CharField(max_length=15, choices=[('inbound', 'Inbound'), ('outbound', 'Outbound'), ('bidirectional', 'Bidirectional')], default='bidirectional')
    total_items = models.PositiveIntegerField(default=0)
    processed_items = models.PositiveIntegerField(default=0)
    succeeded_items = models.PositiveIntegerField(default=0)
    failed_items = models.PositiveIntegerField(default=0)
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    error_summary = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_job_type_display()} - {self.get_status_display()} ({self.connection.name})"

    @property
    def can_retry(self):
        return self.status in ('failed', 'partial') and self.retry_count < self.max_retries


class WebhookEndpoint(models.Model):
    DIRECTION_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='webhook_endpoints')
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE, related_name='webhook_endpoints', null=True, blank=True)
    name = models.CharField(max_length=200)
    url = models.URLField()
    secret = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    event_types = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    headers = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    failure_count = models.PositiveIntegerField(default=0)
    last_triggered = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_direction_display()})"


class WebhookEvent(models.Model):
    DIRECTION_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ]
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
        ('dropped', 'Dropped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='events')
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    schema_version = models.CharField(max_length=10, default='1.0')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    payload = models.JSONField(default=dict)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    signature_valid = models.BooleanField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    last_attempt = models.DateTimeField(null=True, blank=True)
    next_retry = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type']),
            models.Index(fields=['status']),
            models.Index(fields=['idempotency_key']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.get_status_display()}"


class IntegrationLog(models.Model):
    DIRECTION_CHOICES = [
        ('outbound', 'Outbound'),
        ('inbound', 'Inbound'),
    ]
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('rate_limited', 'Rate Limited'),
    ]
    ERROR_CATEGORY_CHOICES = [
        ('authentication', 'Authentication'),
        ('rate_limit', 'Rate Limit'),
        ('validation', 'Validation'),
        ('network', 'Network'),
        ('timeout', 'Timeout'),
        ('external_rejection', 'External Rejection'),
        ('internal_error', 'Internal Error'),
        ('configuration', 'Configuration'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='intg_logs')
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    correlation_id = models.CharField(max_length=255, db_index=True)
    action = models.CharField(max_length=100)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    method = models.CharField(max_length=10, blank=True)
    endpoint_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    status_code = models.IntegerField(null=True, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    internal_id = models.CharField(max_length=255, blank=True)
    request_summary = models.TextField(blank=True)
    response_summary = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    error_category = models.CharField(max_length=30, choices=ERROR_CATEGORY_CHOICES, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['connection', 'created_at']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['status']),
            models.Index(fields=['error_category']),
        ]

    def __str__(self):
        return f"{self.action} - {self.get_status_display()} ({self.created_at})"


class IntegrationError(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='integration_errors')
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name='errors')
    error_type = models.CharField(max_length=50)
    category = models.CharField(max_length=30, choices=IntegrationLog.ERROR_CATEGORY_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    message = models.TextField()
    affected_object_type = models.CharField(max_length=100, blank=True)
    affected_object_id = models.CharField(max_length=255, blank=True)
    retry_available = models.BooleanField(default=False)
    retry_count = models.PositiveIntegerField(default=0)
    last_occurrence = models.DateTimeField(auto_now=True)
    first_occurrence = models.DateTimeField(auto_now_add=True)
    occurrence_count = models.PositiveIntegerField(default=1)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-last_occurrence']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['severity']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.error_type}: {self.message[:80]}"


class ExternalObjectMapping(models.Model):
    ENTITY_CHOICES = [
        ('product', 'Product'),
        ('customer', 'Customer'),
        ('order', 'Order'),
        ('shipment', 'Shipment'),
        ('payment', 'Payment'),
        ('document', 'Document'),
        ('category', 'Category'),
        ('supplier', 'Supplier'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='object_mappings')
    connection = models.ForeignKey(IntegrationConnection, on_delete=models.CASCADE, related_name='object_mappings')
    entity_type = models.CharField(max_length=30, choices=ENTITY_CHOICES)
    internal_id = models.CharField(max_length=255, db_index=True)
    external_id = models.CharField(max_length=255, db_index=True)
    external_system = models.CharField(max_length=100, blank=True)
    internal_data_hash = models.CharField(max_length=64, blank=True)
    external_data_hash = models.CharField(max_length=64, blank=True)
    has_conflict = models.BooleanField(default=False)
    conflict_details = models.JSONField(default=dict, blank=True)
    source_of_truth = models.CharField(max_length=20, choices=[
        ('internal', 'Internal'),
        ('external', 'External'),
        ('manual', 'Manual Review'),
    ], default='internal')
    last_synced = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_synced']
        unique_together = ['company', 'connection', 'entity_type', 'internal_id']
        indexes = [
            models.Index(fields=['company', 'entity_type']),
            models.Index(fields=['internal_id']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return f"{self.entity_type}: {self.internal_id} <-> {self.external_id}"


class APIKey(models.Model):
    SCOPE_CHOICES = [
        ('products.read', 'Products Read'),
        ('products.write', 'Products Write'),
        ('inventory.read', 'Inventory Read'),
        ('inventory.write', 'Inventory Write'),
        ('orders.read', 'Orders Read'),
        ('orders.write', 'Orders Write'),
        ('customers.read', 'Customers Read'),
        ('customers.write', 'Customers Write'),
        ('sales.read', 'Sales Read'),
        ('sales.write', 'Sales Write'),
        ('reports.read', 'Reports Read'),
        ('webhooks.manage', 'Webhooks Manage'),
        ('integrations.manage', 'Integrations Manage'),
        ('finance.read', 'Finance Read'),
        ('documents.read', 'Documents Read'),
        ('documents.write', 'Documents Write'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=200)
    key_hash = models.CharField(max_length=128, unique=True, db_index=True)
    key_prefix = models.CharField(max_length=12, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

    @staticmethod
    def generate_key():
        raw_key = 'sklat_' + secrets.token_hex(28)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        return raw_key, key_hash, key_prefix

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return self.expires_at <= timezone.now()

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired


class IntegrationEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('product.created', 'Product Created'),
        ('product.updated', 'Product Updated'),
        ('product.deleted', 'Product Deleted'),
        ('inventory.changed', 'Inventory Changed'),
        ('order.created', 'Order Created'),
        ('order.confirmed', 'Order Confirmed'),
        ('order.completed', 'Order Completed'),
        ('order.cancelled', 'Order Cancelled'),
        ('payment.created', 'Payment Created'),
        ('payment.completed', 'Payment Completed'),
        ('payment.failed', 'Payment Failed'),
        ('payment.refunded', 'Payment Refunded'),
        ('shipment.created', 'Shipment Created'),
        ('shipment.delivered', 'Shipment Delivered'),
        ('customer.created', 'Customer Created'),
        ('customer.updated', 'Customer Updated'),
        ('document.created', 'Document Created'),
        ('document.status_changed', 'Document Status Changed'),
        ('stock.low', 'Stock Low'),
        ('stock.out', 'Stock Out'),
        ('integration.connected', 'Integration Connected'),
        ('integration.disconnected', 'Integration Disconnected'),
        ('integration.error', 'Integration Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='integration_events')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    schema_version = models.CharField(max_length=10, default='1.0')
    payload = models.JSONField(default=dict)
    source = models.CharField(max_length=100, blank=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'event_type']),
            models.Index(fields=['processed']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.created_at})"


class CircuitBreakerState(models.Model):
    STATE_CHOICES = [
        ('closed', 'Closed'),
        ('open', 'Open'),
        ('half_open', 'Half Open'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.OneToOneField(IntegrationConnection, on_delete=models.CASCADE, related_name='circuit_state')
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default='closed')
    failure_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    last_failure = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    half_open_max_attempts = models.PositiveIntegerField(default=3)
    failure_threshold = models.PositiveIntegerField(default=5)
    recovery_timeout_seconds = models.PositiveIntegerField(default=300)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Circuit {self.get_state_display()} - {self.connection.name}"

    @property
    def should_attempt(self):
        if self.state == 'closed':
            return True
        if self.state == 'open' and self.opened_at:
            elapsed = (timezone.now() - self.opened_at).total_seconds()
            if elapsed >= self.recovery_timeout_seconds:
                return True
        if self.state == 'half_open':
            return self.success_count < self.half_open_max_attempts
        return False
