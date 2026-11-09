from django.contrib import admin
from .models import AutomationRule, AutomationExecution, AutomationEvent, AutomationSchedule


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'trigger_type', 'status', 'priority', 'execution_count', 'created_at']
    list_filter = ['status', 'priority', 'trigger_type']
    search_fields = ['name', 'code']
    raw_id_fields = ['company', 'created_by', 'updated_by']


@admin.register(AutomationExecution)
class AutomationExecutionAdmin(admin.ModelAdmin):
    list_display = ['rule', 'event_type', 'status', 'duration_ms', 'actions_succeeded', 'actions_failed', 'created_at']
    list_filter = ['status']
    raw_id_fields = ['rule', 'company']
    readonly_fields = ['event_id']


@admin.register(AutomationEvent)
class AutomationEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'object_type', 'object_id', 'processed', 'created_at']
    list_filter = ['event_type', 'processed']
    raw_id_fields = ['company']
    readonly_fields = ['event_id']
