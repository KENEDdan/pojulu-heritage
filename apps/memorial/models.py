# apps/memorial/models.py
from django.db import models
from django.urls import reverse


class MemorialRecord(models.Model):
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

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Memorial Record'

    def __str__(self):
        return f"In Memoriam: {self.person.full_name}"

    def get_absolute_url(self):
        return reverse('memorial:detail', kwargs={'pk': self.pk})
