from django.contrib import admin
from .models import ElderInterview


@admin.register(ElderInterview)
class ElderInterviewAdmin(admin.ModelAdmin):
    list_display      = ['elder_name', 'clan', 'interview_date', 'interviewer', 'is_published', 'is_featured']
    list_filter       = ['clan', 'is_published', 'is_featured']
    search_fields     = ['elder_name', 'summary', 'transcript', 'topics_covered']
    list_editable     = ['is_published', 'is_featured']
    raw_id_fields     = ['elder_person', 'clan']
    filter_horizontal = ['clans_mentioned']
    readonly_fields   = ['created_at', 'updated_at']
    fieldsets = (
        ('Elder Identity',  {'fields': ('elder_name', 'elder_person', 'clan', 'payam', 'approximate_age', 'photo_of_elder')}),
        ('Interview',       {'fields': ('interview_date', 'interview_location', 'interviewer', 'language')}),
        ('Content',         {'fields': ('summary', 'topics_covered', 'transcript')}),
        ('Media',           {'fields': ('audio_file', 'video_file', 'video_url'), 'classes': ('collapse',)}),
        ('Clans Mentioned', {'fields': ('clans_mentioned',), 'classes': ('collapse',)}),
        ('Publishing',      {'fields': ('is_published', 'is_featured', 'created_at', 'updated_at')}),
    )