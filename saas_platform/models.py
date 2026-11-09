import uuid
import hashlib
import secrets
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator


# ============================================================
# 1. SUBSCRIPTION PLANS
# ============================================================
class SubscriptionPlan(models.Model):
    """SaaS subscription plan definitions."""
    INTERVAL_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')

    max_users = models.PositiveIntegerField(default=5)
    max_products = models.PositiveIntegerField(default=1000)
    max_warehouses = models.PositiveIntegerField(default=3)
    max_orders_monthly = models.PositiveIntegerField(default=500)
    max_storage_mb = models.PositiveIntegerField(default=500)
    max_api_calls_daily = models.PositiveIntegerField(default=1000)
    max_ai_requests_monthly = models.PositiveIntegerField(default=100)
    max_automation_rules = models.PositiveIntegerField(default=10)

    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription_plans'
        ordering = ['display_order', 'price_monthly']

    def __str__(self):
        return self.name


# ============================================================
# 2. COMPANY SUBSCRIPTION
# ============================================================
class CompanySubscription(models.Model):
    """Tracks a company's active subscription."""
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField('users.Company', on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    trial_started = models.DateTimeField(null=True, blank=True)
    trial_ends = models.DateTimeField(null=True, blank=True)
    subscription_started = models.DateTimeField(null=True, blank=True)
    subscription_ends = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    external_subscription_id = models.CharField(max_length=255, blank=True, default='')
    auto_renew = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_subscriptions'

    def __str__(self):
        return f"{self.company} - {self.plan} ({self.status})"

    @property
    def is_trial_active(self):
        if self.status != 'trial' or not self.trial_ends:
            return False
        return timezone.now() < self.trial_ends

    @property
    def is_subscription_active(self):
        return self.status in ('trial', 'active')

    def start_trial(self, days=14):
        self.status = 'trial'
        self.trial_started = timezone.now()
        self.trial_ends = timezone.now() + timezone.timedelta(days=days)
        self.save(update_fields=['status', 'trial_started', 'trial_ends', 'updated_at'])


# ============================================================
# 3. USAGE TRACKING
# ============================================================
class UsageLog(models.Model):
    """Tracks resource usage per company per day."""
    RESOURCE_CHOICES = [
        ('users', 'Users'),
        ('products', 'Products'),
        ('warehouses', 'Warehouses'),
        ('orders_monthly', 'Orders Monthly'),
        ('storage_mb', 'Storage MB'),
        ('api_calls_daily', 'API Calls Daily'),
        ('ai_requests_monthly', 'AI Requests Monthly'),
        ('automation_executions', 'Automation Executions'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='usage_logs')
    resource = models.CharField(max_length=30, choices=RESOURCE_CHOICES)
    date = models.DateField(default=timezone.now)
    count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usage_logs'
        unique_together = ['company', 'resource', 'date']
        indexes = [
            models.Index(fields=['company', 'resource', 'date']),
        ]

    def __str__(self):
        return f"{self.company} - {self.resource}: {self.count} ({self.date})"


# ============================================================
# 4. FEATURE FLAGS
# ============================================================
class FeatureFlag(models.Model):
    """Feature flag system for gradual rollouts."""
    SCOPE_CHOICES = [
        ('global', 'Global'),
        ('plan', 'Plan'),
        ('company', 'Company'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='global')
    enabled = models.BooleanField(default=False)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, null=True, blank=True)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'feature_flags'
        indexes = [
            models.Index(fields=['key', 'scope']),
            models.Index(fields=['enabled']),
        ]

    def __str__(self):
        return f"{self.key} ({'ON' if self.enabled else 'OFF'})"

    @classmethod
    def is_enabled(cls, key, company=None, plan=None):
        try:
            flag = cls.objects.get(key=key)
        except cls.DoesNotExist:
            return False

        if flag.scope == 'global':
            return flag.enabled
        elif flag.scope == 'plan' and plan:
            return flag.enabled and flag.plan_id == plan.pk
        elif flag.scope == 'company' and company:
            return flag.enabled and flag.company_id == company.pk
        return False


# ============================================================
# 5. AUDIT LOG
# ============================================================
class AuditLog(models.Model):
    """Immutable audit trail for security and compliance."""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('login_failed', 'Login Failed'),
        ('password_change', 'Password Change'),
        ('password_reset', 'Password Reset'),
        ('permission_change', 'Permission Change'),
        ('role_change', 'Role Change'),
        ('company_switch', 'Company Switch'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('financial_action', 'Financial Action'),
        ('inventory_adjustment', 'Inventory Adjustment'),
        ('order_action', 'Order Action'),
        ('integration_change', 'Integration Change'),
        ('automation_change', 'Automation Change'),
        ('ai_action', 'AI Action'),
        ('document_download', 'Document Download'),
        ('api_key_create', 'API Key Create'),
        ('api_key_revoke', 'API Key Revoke'),
        ('subscription_change', 'Subscription Change'),
        ('suspicious_activity', 'Suspicious Activity'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('users.Company', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100, blank=True, default='')
    resource_id = models.CharField(max_length=255, blank=True, default='')
    resource_name = models.CharField(max_length=255, blank=True, default='')
    description = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    request_id = models.CharField(max_length=36, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'action']),
            models.Index(fields=['user', 'action']),
            models.Index(fields=['created_at']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['action', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.action}] {self.resource_type}:{self.resource_id} by {self.user} at {self.created_at}"

    @classmethod
    def log(cls, action, company=None, user=None, resource_type='', resource_id='',
            resource_name='', description='', request=None, metadata=None):
        ip = None
        ua = ''
        request_id = ''
        if request:
            ip = cls._get_client_ip(request)
            ua = str(request.META.get('HTTP_USER_AGENT', ''))[:500]
            request_id = getattr(request, 'request_id', '')
        return cls.objects.create(
            company=company or getattr(user, 'company', None),
            user=user, action=action,
            resource_type=resource_type, resource_id=str(resource_id),
            resource_name=resource_name, description=description,
            ip_address=ip, user_agent=ua, request_id=request_id,
            metadata=metadata or {},
        )

    @classmethod
    def _get_client_ip(cls, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# ============================================================
# 6. ROLE-PERMISSION SYSTEM
# ============================================================
class Permission(models.Model):
    """Granular permission definition."""
    MODULE_CHOICES = [
        ('products', 'Products'), ('inventory', 'Inventory'),
        ('warehouses', 'Warehouses'), ('purchases', 'Purchases'),
        ('sales', 'Sales'), ('orders', 'Orders'),
        ('crm', 'CRM'), ('finance', 'Finance'),
        ('pos', 'POS'), ('wms', 'WMS'),
        ('logistics', 'Logistics'), ('reports', 'Reports'),
        ('documents', 'Documents'), ('integrations', 'Integrations'),
        ('automation', 'Automation'), ('ai', 'AI'),
        ('users', 'Users'), ('company', 'Company'),
        ('platform', 'Platform'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codename = models.CharField(max_length=100)
    module = models.CharField(max_length=30, choices=MODULE_CHOICES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    is_platform_only = models.BooleanField(default=False)

    class Meta:
        db_table = 'permissions'
        ordering = ['module', 'codename']
        unique_together = ['codename', 'module']

    def __str__(self):
        return f"{self.module}.{self.codename}"


class Role(models.Model):
    """Company-scoped role with assigned permissions."""
    SCOPE_CHOICES = [
        ('platform', 'Platform'),
        ('company', 'Company'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, null=True, blank=True, related_name='roles')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='company')
    description = models.TextField(blank=True, default='')
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')
    is_system = models.BooleanField(default=False, help_text='System roles cannot be deleted')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'roles'
        unique_together = ['slug', 'company']

    def __str__(self):
        scope = ' [Platform]' if self.scope == 'platform' else f' [{self.company}]' if self.company else ''
        return f"{self.name}{scope}"

    def has_permission(self, codename):
        return self.permissions.filter(codename=codename).exists()


class UserRole(models.Model):
    """Assigns a role to a user within a company."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='user_roles')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_roles')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'user_roles'
        unique_together = ['user', 'role', 'company']

    def __str__(self):
        return f"{self.user} -> {self.role} [{self.company}]"


# ============================================================
# 7. USER INVITATIONS
# ============================================================
class UserInvitation(models.Model):
    """Company user invitation system."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='invitations')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    role_legacy = models.CharField(max_length=20, blank=True, default='', help_text='Legacy role choice for backward compat')
    token = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sent_invitations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True, default='')
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_invitations'

    def __str__(self):
        return f"Invite: {self.email} -> {self.company} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def accept(self):
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_at'])


# ============================================================
# 8. COMPANY MEMBERSHIP (for multi-company users)
# ============================================================
class CompanyMembership(models.Model):
    """Tracks user membership across companies."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('invited', 'Invited'),
        ('suspended', 'Suspended'),
        ('removed', 'Removed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    company = models.ForeignKey('users.Company', on_delete=models.CASCADE, related_name='memberships')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_current = models.BooleanField(default=False)

    class Meta:
        db_table = 'company_memberships'
        unique_together = ['user', 'company']

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.status})"


# ============================================================
# 9. SYSTEM HEALTH CHECK
# ============================================================
class HealthCheck(models.Model):
    """Records system health check results."""
    COMPONENT_CHOICES = [
        ('application', 'Application'),
        ('database', 'Database'),
        ('cache', 'Cache'),
        ('storage', 'Storage'),
        ('background_jobs', 'Background Jobs'),
    ]
    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('degraded', 'Degraded'),
        ('unhealthy', 'Unhealthy'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component = models.CharField(max_length=30, choices=COMPONENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField(blank=True, default='')
    response_time_ms = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'health_checks'
        ordering = ['-checked_at']

    def __str__(self):
        return f"{self.component}: {self.status} at {self.checked_at}"


# ============================================================
# 10. API RATE LIMITING
# ============================================================
class RateLimitRecord(models.Model):
    """Per-key rate limiting for API endpoints."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=255, db_index=True)
    window = models.CharField(max_length=20)
    request_count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()

    class Meta:
        db_table = 'rate_limit_records'
        unique_together = ['key', 'window']

    def __str__(self):
        return f"{self.key}: {self.request_count} in {self.window}"
