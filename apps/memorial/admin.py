from django.contrib import admin
from .models import MemorialRecord


@admin.register(MemorialRecord)
class MemorialAdmin(admin.ModelAdmin):
    list_display    = ['__str__', 'is_featured', 'submitted_by', 'created_at']
    list_filter     = ['is_featured', 'person__clan']
    search_fields   = ['person__first_name', 'person__last_name', 'tribute']
    list_editable   = ['is_featured']
    raw_id_fields   = ['person']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Person',    {'fields': ('person',)}),
        ('Tribute',   {'fields': ('tribute', 'epitaph')}),
        ('Details',   {'fields': ('survived_by', 'burial_place')}),
        ('Publishing',{'fields': ('is_featured', 'submitted_by', 'created_at')}),
    )