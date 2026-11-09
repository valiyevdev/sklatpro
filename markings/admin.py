from django.contrib import admin
from .models import GTIN, MarkingCode, MarkingCodeHistory, Aggregation, AggregationItem, CodeValidation


@admin.register(GTIN)
class GTINAdmin(admin.ModelAdmin):
    list_display = ['gtin', 'product', 'format_type', 'is_primary', 'is_active', 'created_at']
    list_filter = ['format_type', 'is_primary', 'is_active', 'created_at']
    search_fields = ['gtin', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    list_per_page = 25


class MarkingCodeHistoryInline(admin.TabularInline):
    model = MarkingCodeHistory
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'event_type', 'reference_type', 'reference_id',
                       'warehouse', 'location', 'quantity', 'notes', 'performed_by', 'performed_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MarkingCode)
class MarkingCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'product', 'serial_number', 'status', 'verification_status', 'warehouse', 'created_at']
    list_filter = ['status', 'verification_status', 'warehouse', 'created_at']
    search_fields = ['code', 'serial_number', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    list_per_page = 25
    inlines = [MarkingCodeHistoryInline]


@admin.register(MarkingCodeHistory)
class MarkingCodeHistoryAdmin(admin.ModelAdmin):
    list_display = ['marking_code', 'from_status', 'to_status', 'event_type', 'performed_by', 'performed_at']
    list_filter = ['event_type', 'to_status', 'performed_at']
    search_fields = ['marking_code__code']
    readonly_fields = ['performed_at']
    ordering = ['-performed_at']
    list_per_page = 25


class AggregationItemInline(admin.TabularInline):
    model = AggregationItem
    extra = 0
    readonly_fields = ['added_at']


@admin.register(Aggregation)
class AggregationAdmin(admin.ModelAdmin):
    list_display = ['parent_code', 'product', 'quantity', 'status', 'warehouse', 'created_at']
    list_filter = ['status', 'warehouse', 'created_at']
    search_fields = ['parent_code', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    list_per_page = 25
    inlines = [AggregationItemInline]


@admin.register(AggregationItem)
class AggregationItemAdmin(admin.ModelAdmin):
    list_display = ['aggregation', 'marking_code', 'quantity', 'added_at']
    search_fields = ['aggregation__parent_code', 'marking_code__code']
    readonly_fields = ['added_at']
    list_per_page = 25


@admin.register(CodeValidation)
class CodeValidationAdmin(admin.ModelAdmin):
    list_display = ['code_input', 'code_type', 'result', 'verified_by', 'verified_at']
    list_filter = ['code_type', 'result', 'verified_at']
    search_fields = ['code_input']
    readonly_fields = ['verified_at']
    ordering = ['-verified_at']
    list_per_page = 25
