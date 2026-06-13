from django.contrib import admin
from .models import AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'role', 'is_active', 'assigned_by', 'created_at']
    list_filter   = ['role', 'is_active']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    list_editable = ['is_active']
    raw_id_fields = ['user', 'assigned_by']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Account', {'fields': ('user', 'role', 'is_active')}),
        ('Details', {'fields': ('phone', 'notes', 'assigned_by', 'created_at')}),
    )