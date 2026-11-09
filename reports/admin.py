from django.contrib import admin
from .models import SavedReport, ReportSchedule


@admin.register(SavedReport)
class SavedReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'report_type', 'company', 'owner', 'visibility', 'created_at']
    list_filter = ['report_type', 'visibility']
    search_fields = ['name']


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ['saved_report', 'frequency', 'is_active', 'last_run', 'next_run']
    list_filter = ['frequency', 'is_active']
