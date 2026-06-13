from django.contrib import admin
from .models import Marriage


@admin.register(Marriage)
class MarriageAdmin(admin.ModelAdmin):
    list_display    = ['husband_display', 'wife_display', 'husband_clan_display', 'wife_clan_display', 'year', 'is_verified']
    list_filter     = ['husband_clan', 'wife_clan', 'is_verified']
    search_fields   = ['husband_name', 'wife_name']
    list_editable   = ['is_verified']
    raw_id_fields   = ['husband', 'wife', 'husband_clan', 'wife_clan']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Husband', {'fields': ('husband', 'husband_name', 'husband_clan', 'husband_community')}),
        ('Wife',    {'fields': ('wife', 'wife_name', 'wife_clan', 'wife_community')}),
        ('Union',   {'fields': ('year', 'place', 'payam', 'children_names', 'notes')}),
        ('Status',  {'fields': ('is_verified', 'created_at')}),
    )