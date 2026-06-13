from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

SUBMISSION_TYPE_CHOICES = [
    ('person',      'Person / Family Member'),
    ('clan',        'Clan History'),
    ('memorial',    'Memorial Record'),
    ('marriage',    'Marriage Record'),
    ('achievement', 'Achievement'),
    ('cultural',    'Cultural Record'),
    ('elder',       'Elder Interview Request'),
    ('correction',  'Correction / Update to Existing Record'),
]

STATUS_CHOICES = [
    ('pending',      'Pending Review'),
    ('in_review',    'Under Review'),
    ('approved',     'Approved & Published'),
    ('rejected',     'Rejected'),
    ('needs_info',   'More Information Needed'),
]


class Submission(models.Model):
    # What kind of record
    submission_type       = models.CharField(max_length=30, choices=SUBMISSION_TYPE_CHOICES)

    # Submitter info
    submitter_name        = models.CharField(max_length=200)
    submitter_email       = models.EmailField()
    submitter_phone       = models.CharField(max_length=50, blank=True)
    submitter_location    = models.CharField(max_length=200, blank=True)
    submitter_relationship = models.CharField(max_length=300,
                                               help_text="Your relationship to this record (e.g. grandson, clan coordinator)")

    # The submitted data as structured fields
    subject_name          = models.CharField(max_length=300, blank=True,
                                              help_text="Name of the person/clan/record being submitted")
    clan_name             = models.CharField(max_length=200, blank=True)
    payam                 = models.CharField(max_length=100, blank=True)
    year                  = models.CharField(max_length=20, blank=True)

    # Main content
    content               = models.TextField(help_text="Main information / narrative for this submission")
    additional_notes      = models.TextField(blank=True)

    # Attachments
    attachment            = models.FileField(upload_to='submissions/attachments/',
                                              blank=True, null=True,
                                              help_text="Document, photo, or audio file")

    # Workflow
    status                = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                              default='pending')
    reviewer_notes        = models.TextField(blank=True,
                                              help_text="Internal notes from the reviewer")
    reviewed_by           = models.ForeignKey(User, null=True, blank=True,
                                               on_delete=models.SET_NULL,
                                               related_name='reviewed_submissions')
    reviewed_at           = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Community Submission'
        verbose_name_plural = 'Community Submissions'

    def __str__(self):
        return f"[{self.get_submission_type_display()}] {self.subject_name} — {self.submitter_name}"

    @property
    def status_badge_class(self):
        return {
            'pending':    'warning',
            'in_review':  'info',
            'approved':   'success',
            'rejected':   'danger',
            'needs_info': 'secondary',
        }.get(self.status, 'secondary')
