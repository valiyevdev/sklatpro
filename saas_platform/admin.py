from django.contrib import admin
from .models import (
    SubscriptionPlan, CompanySubscription, UsageLog, FeatureFlag,
    AuditLog, Permission, Role, UserRole, UserInvitation,
    CompanyMembership, HealthCheck, RateLimitRecord,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_monthly', 'price_yearly', 'max_users', 'is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(CompanySubscription)
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'plan', 'status', 'trial_ends', 'subscription_ends', 'created_at')
    list_filter = ('status',)
    search_fields = ('company__company_name',)


@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ('company', 'resource', 'count', 'date')
    list_filter = ('resource', 'date')


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ('key', 'name', 'scope', 'enabled', 'created_at')
    list_filter = ('scope', 'enabled')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'resource_type', 'user', 'company', 'ip_address', 'created_at')
    list_filter = ('action',)
    search_fields = ('resource_type', 'resource_id', 'description')
    readonly_fields = [f.name for f in AuditLog._meta.fields]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'module', 'name', 'is_platform_only')
    list_filter = ('module', 'is_platform_only')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope', 'company', 'is_system', 'is_active')
    list_filter = ('scope', 'is_system', 'is_active')
    filter_horizontal = ('permissions',)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'company', 'is_active', 'assigned_at')
    list_filter = ('is_active',)


@admin.register(UserInvitation)
class UserInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'status', 'created_at', 'expires_at')
    list_filter = ('status',)


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'status', 'is_current', 'joined_at')
    list_filter = ('status', 'is_current')


@admin.register(HealthCheck)
class HealthCheckAdmin(admin.ModelAdmin):
    list_display = ('component', 'status', 'response_time_ms', 'checked_at')
    list_filter = ('component', 'status')


@admin.register(RateLimitRecord)
class RateLimitRecordAdmin(admin.ModelAdmin):
    list_display = ('key', 'window', 'request_count', 'window_start')
