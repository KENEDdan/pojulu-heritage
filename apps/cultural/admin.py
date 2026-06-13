from django.contrib import admin
from .models import CulturalRecord


@admin.register(CulturalRecord)
class CulturalAdmin(admin.ModelAdmin):
    list_display    = ['title', 'record_type', 'clan', 'language', 'is_verified', 'is_featured']
    list_filter     = ['record_type', 'is_verified', 'is_featured', 'clan']
    search_fields   = ['title', 'content', 'translation']
    list_editable   = ['is_verified', 'is_featured']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Identity',   {'fields': ('title', 'slug', 'record_type', 'clan', 'language')}),
        ('Content',    {'fields': ('content', 'translation', 'context', 'performers')}),
        ('Media',      {'fields': ('audio_file', 'video_url', 'image'), 'classes': ('collapse',)}),
        ('Source',     {'fields': ('source',), 'classes': ('collapse',)}),
        ('Publishing', {'fields': ('is_verified', 'is_featured', 'created_at', 'updated_at')}),
    )