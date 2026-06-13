from django.db import models
from django.utils import timezone

# Pojulu settlement locations — Lainya County, Central Equatoria State
LOCATION_CHOICES = [
    ('lainya_centre', 'Lainya Centre (Headquarters)'),
    ('kupera',        'Kupera'),
    ('kenyi',         'Kenyi'),
    ('wuji',          'Wuji'),
    ('mukaya',        'Mukaya'),
    ('wonduruba',     'Wonduruba (Juba County)'),
    ('yei_county',    'Yei County'),
    ('diaspora',      'Diaspora'),
    ('other',         'Other'),
]

# Backwards-compatible alias used in existing models
PAYAM_CHOICES = LOCATION_CHOICES


class Announcement(models.Model):
    title   = models.CharField(max_length=300)
    body    = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class SiteStats(models.Model):
    """Cached statistics displayed on the homepage."""
    clans_count    = models.PositiveIntegerField(default=0)
    families_count = models.PositiveIntegerField(default=0)
    persons_count  = models.PositiveIntegerField(default=0)
    memorial_count = models.PositiveIntegerField(default=0)
    interviews_count = models.PositiveIntegerField(default=0)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Statistics'
        verbose_name_plural = 'Site Statistics'

    def __str__(self):
        return f'Stats (updated {self.updated_at:%d %b %Y})'
