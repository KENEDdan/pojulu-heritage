from django.db import models
from django.urls import reverse

RECORD_TYPE_CHOICES = [
    ('song',      'Traditional Song'),
    ('proverb',   'Proverb & Wisdom'),
    ('ceremony',  'Cultural Ceremony'),
    ('story',     'Story & Oral Narrative'),
    ('folklore',  'Folklore & Myth'),
    ('dance',     'Traditional Dance'),
    ('language',  'Language & Linguistics'),
    ('other',     'Other'),
]

TYPE_ICONS = {
    'song':      '🎵',
    'proverb':   '📖',
    'ceremony':  '🎋',
    'story':     '🌿',
    'folklore':  '🌙',
    'dance':     '💃',
    'language':  '🗣️',
    'other':     '🌍',
}


class CulturalRecord(models.Model):
    title         = models.CharField(max_length=300)
    slug          = models.SlugField(max_length=320, unique=True, blank=True)
    record_type   = models.CharField(max_length=20, choices=RECORD_TYPE_CHOICES)
    clan          = models.ForeignKey('clans.Clan', null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       help_text="Clan this record is associated with")
    content       = models.TextField(help_text="The main content — lyrics, text, description")
    translation   = models.TextField(blank=True,
                                      help_text="English translation if in Pojulu language")
    context       = models.TextField(blank=True,
                                      help_text="When, how, and why this is used / performed")
    performers    = models.CharField(max_length=300, blank=True,
                                      help_text="Who traditionally performs or recites this")
    audio_file    = models.FileField(upload_to='cultural/audio/', blank=True, null=True)
    video_url     = models.URLField(blank=True, help_text="YouTube/Vimeo link to a recording")
    image         = models.ImageField(upload_to='cultural/images/', blank=True, null=True)
    language      = models.CharField(max_length=100, default='Pojulu')
    source        = models.CharField(max_length=300, blank=True,
                                      help_text="Source: elder name, interview date, document ref")
    is_verified   = models.BooleanField(default=False)
    is_featured   = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['record_type', 'title']
        verbose_name = 'Cultural Record'

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug, n = base, 1
            while CulturalRecord.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.get_record_type_display()}] {self.title}"

    def get_absolute_url(self):
        return reverse('cultural:detail', kwargs={'slug': self.slug})

    @property
    def icon(self):
        return TYPE_ICONS.get(self.record_type, '🌍')

    @property
    def has_audio(self):
        return bool(self.audio_file)

    @property
    def has_video(self):
        return bool(self.video_url)
