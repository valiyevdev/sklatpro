from django.contrib import admin
from .models import Activity

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['activity_type', 'user', 'description', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['description', 'user__username']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

