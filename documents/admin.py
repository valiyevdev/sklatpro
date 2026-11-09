from django.contrib import admin
from .models import (
    Document, DocumentItem, DocumentAttachment,
    DocumentVersion, DocumentTemplate, DocumentSignature,
    EDOConfig, EDOTransaction,
)


class DocumentItemInline(admin.TabularInline):
    model = DocumentItem
    extra = 0
    fields = ['product', 'description', 'quantity', 'unit_price', 'discount', 'tax', 'line_total']


class DocumentAttachmentInline(admin.TabularInline):
    model = DocumentAttachment
    extra = 0
    readonly_fields = ['file', 'filename', 'file_size', 'content_type', 'uploaded_by', 'uploaded_at']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['number', 'doc_type', 'title', 'status', 'date', 'customer', 'supplier', 'total', 'company']
    list_filter = ['doc_type', 'status', 'company', 'date', 'is_electronic']
    search_fields = ['number', 'title', 'customer__name', 'supplier__name']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    inlines = [DocumentItemInline, DocumentAttachmentInline]
    list_per_page = 50


@admin.register(DocumentItem)
class DocumentItemAdmin(admin.ModelAdmin):
    list_display = ['document', 'product', 'description', 'quantity', 'unit_price', 'line_total', 'company']
    list_filter = ['company']
    search_fields = ['document__number', 'description', 'product__name']
    raw_id_fields = ['document', 'product']


@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'document', 'file_size', 'uploaded_by', 'uploaded_at']
    list_filter = ['company']
    search_fields = ['filename', 'document__number']


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['document', 'version_number', 'status', 'total', 'created_by', 'created_at']
    list_filter = ['company']
    search_fields = ['document__number']


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'doc_type', 'is_default', 'is_active', 'company']
    list_filter = ['doc_type', 'is_active', 'is_default', 'company']
    search_fields = ['name']


@admin.register(DocumentSignature)
class DocumentSignatureAdmin(admin.ModelAdmin):
    list_display = ['document', 'signer', 'status', 'signed_at', 'company']
    list_filter = ['status', 'company']
    search_fields = ['document__number', 'signer__email']


@admin.register(EDOConfig)
class EDOConfigAdmin(admin.ModelAdmin):
    list_display = ['provider_name', 'provider_code', 'is_active', 'company']
    list_filter = ['is_active', 'company']
    search_fields = ['provider_name', 'provider_code']


@admin.register(EDOTransaction)
class EDOTransactionAdmin(admin.ModelAdmin):
    list_display = ['document', 'action', 'direction', 'status', 'created_at', 'company']
    list_filter = ['status', 'action', 'direction', 'company']
    search_fields = ['document__number', 'external_id']
    readonly_fields = ['idempotency_key', 'created_at', 'completed_at']
