from django import forms
from .models import Submission, SUBMISSION_TYPE_CHOICES
from apps.core.models import LOCATION_CHOICES as PAYAM_CHOICES


class SubmissionForm(forms.ModelForm):
    submission_type = forms.ChoiceField(
        choices=SUBMISSION_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )

    class Meta:
        model = Submission
        fields = [
            'submission_type',
            'submitter_name', 'submitter_email', 'submitter_phone',
            'submitter_location', 'submitter_relationship',
            'subject_name', 'clan_name', 'payam', 'year',
            'content', 'additional_notes', 'attachment',
        ]
        widgets = {
            'submitter_name':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'submitter_email':         forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'submitter_phone':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+211 ...'}),
            'submitter_location':      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City / Country'}),
            'submitter_relationship':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Grandson, Clan Coordinator, Community Member'}),
            'subject_name':            forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name of person / clan / record'}),
            'clan_name':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Clan name'}),
            'payam':                   forms.Select(choices=[('','— Select Payam —')] + list(PAYAM_CHOICES), attrs={'class': 'form-select'}),
            'year':                    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 1965 or approx. 1970s'}),
            'content':                 forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': 'Share everything you know. The more detail, the richer the record.'}),
            'additional_notes':        forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Any additional context, sources, or notes for the editorial team…'}),
            'attachment':              forms.FileInput(attrs={'class': 'form-control'}),
        }
