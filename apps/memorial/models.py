# apps/memorial/models.py
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords
from apps.core.softdelete import SoftDeleteModel, soft_delete_managers
from django.urls import reverse


class MemorialQuerySet(models.QuerySet):
    def public(self):
        # A memorial is public when the person it honours is.
        return (self.filter(person__is_verified=True, person__is_deleted=False)
                .exclude(person__is_private=True, person__is_deceased=False))


class MemorialRecord(SoftDeleteModel):
    person        = models.OneToOneField('genealogy.Person', on_delete=models.CASCADE,
                                          related_name='memorial')
    tribute       = models.TextField(help_text="Extended tribute / remembrance text")
    survived_by   = models.TextField(blank=True,
                                      help_text="List of surviving family members")
    burial_place  = models.CharField(max_length=300, blank=True)
    epitaph       = models.CharField(max_length=300, blank=True,
                                      help_text="Short memorable quote or epitaph")
    submitted_by  = models.CharField(max_length=200, blank=True)
    is_featured   = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)

    objects, all_objects = soft_delete_managers(MemorialQuerySet)
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Memorial Record'

    def __str__(self):
        return f"In Memoriam: {self.person.full_name}"

    def clean(self):
        super().clean()
        if self.person_id and MemorialRecord.all_objects.filter(person_id=self.person_id, is_deleted=True) \
                .exclude(pk=self.pk).exists():
            raise ValidationError({'person': 'A memorial for this person is in the Trash. Restore it instead.'})

    def get_absolute_url(self):
        return reverse('memorial:detail', kwargs={'pk': self.pk})
