from django.contrib import admin
from .models import (
    CustomerSegment, CustomerTag, CustomerSegmentAssignment,
    CustomerTagAssignment, CustomerCommunication, CustomerNote,
    CustomerDocument, CustomerTask,
)


@admin.register(CustomerSegment)
class CustomerSegmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'is_active', 'created_at']
    list_filter = ['company', 'is_active']


@admin.register(CustomerTag)
class CustomerTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'color']
    list_filter = ['company']


@admin.register(CustomerCommunication)
class CustomerCommunicationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'channel', 'comm_type', 'status', 'created_by', 'created_at']
    list_filter = ['channel', 'comm_type', 'status']


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ['customer', 'category', 'title', 'is_important', 'created_at']
    list_filter = ['category', 'is_important']


@admin.register(CustomerTask)
class CustomerTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'customer', 'task_type', 'priority', 'status', 'due_date']
    list_filter = ['task_type', 'priority', 'status']
