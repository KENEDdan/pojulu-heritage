from django.contrib import admin
from django.utils import timezone
from .models import Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display    = ['subject_name', 'submission_type', 'submitter_name', 'submitter_email', 'status', 'created_at']
    list_filter     = ['submission_type', 'status']
    search_fields   = ['subject_name', 'submitter_name', 'submitter_email', 'content']
    list_editable   = ['status']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy  = 'created_at'
    fieldsets = (
        ('Record Information', {
            'fields': ('submission_type', 'subject_name', 'clan_name', 'payam', 'year', 'content', 'additional_notes', 'attachment')
        }),
        ('Submitter Details', {
            'fields': ('submitter_name', 'submitter_email', 'submitter_phone', 'submitter_location', 'submitter_relationship')
        }),
        ('Review', {
            'fields': ('status', 'reviewer_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)