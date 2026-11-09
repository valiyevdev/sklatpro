from django.contrib import admin
from .models import SpiskalarList, SpiskalarItem, Task, ChecklistItem, TaskComment, TaskAttachment, TaskTemplate


class SpiskalarItemInline(admin.TabularInline):
    model = SpiskalarItem
    extra = 0


@admin.register(SpiskalarList)
class SpiskalarListAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'status', 'priority', 'assigned_to', 'due_date', 'company')
    list_filter = ('type', 'status', 'priority')
    search_fields = ('name',)
    inlines = [SpiskalarItemInline]


class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'task_type', 'status', 'priority', 'assigned_to', 'due_date', 'company')
    list_filter = ('task_type', 'status', 'priority')
    search_fields = ('title', 'description')
    inlines = [ChecklistItemInline]


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'created_at')
    list_filter = ('created_at',)


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'task', 'uploaded_by', 'uploaded_at')


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'task_type', 'priority', 'company')
    list_filter = ('task_type', 'priority')
