from django.contrib import admin
from .models import Achievement


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display    = ['person_name', 'category', 'year', 'clan', 'is_verified', 'is_featured']
    list_filter     = ['category', 'is_verified', 'is_featured', 'clan']
    search_fields   = ['person_name', 'title', 'description']
    list_editable   = ['is_verified', 'is_featured']
    date_hierarchy  = None
    readonly_fields = ['created_at']
    fieldsets = (
        ('Person',      {'fields': ('person_name', 'person', 'clan')}),
        ('Achievement', {'fields': ('category', 'title', 'description', 'year', 'source')}),
        ('Status',      {'fields': ('is_verified', 'is_featured', 'created_at')}),
    )