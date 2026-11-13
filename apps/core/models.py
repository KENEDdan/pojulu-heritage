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


# ── EVIDENCE / ATTACHMENTS ───────────────────────────────────────────────────
# One upload model shared by every kind of record (families, chiefs,
# landmarks, memorials, achievements, marriages, interviews, ...). Files live
# in private storage and are served by the media gate, which shows them to the
# public only when the attachment is marked public AND its record is public.

from django.contrib.contenttypes.fields import GenericForeignKey  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from simple_history.models import HistoricalRecords  # noqa: E402

from .storage import get_private_storage  # noqa: E402
from .uploads import SafeFileField, UploadTo  # noqa: E402
from .validators import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, extension_of, validate_media  # noqa: E402


class AttachmentQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_public=True)


class Attachment(models.Model):
    KIND_CHOICES = [
        ('photo',    'Photo'),
        ('document', 'Document / certificate / letter'),
        ('audio',    'Audio recording'),
        ('video',    'Video'),
        ('link',     'Link to an outside source'),
    ]
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.PositiveBigIntegerField()
    record       = GenericForeignKey('content_type', 'object_id')

    kind         = models.CharField(max_length=20, choices=KIND_CHOICES, default='photo')
    title        = models.CharField(max_length=300, blank=True)
    file         = SafeFileField(upload_to=UploadTo('attachments'), blank=True, null=True,
                                 storage=get_private_storage, validators=[validate_media],
                                 help_text='Photo, PDF/Word document, audio or video')
    external_url = models.URLField(blank=True, help_text='Or a link to where the evidence is kept online')
    caption      = models.TextField(blank=True, help_text='What this shows and why it matters')
    source       = models.CharField(max_length=300, blank=True,
                                    help_text='Who provided it, or where it comes from')
    date_taken   = models.CharField(max_length=100, blank=True, help_text='Date or approximate year')
    is_public    = models.BooleanField(default=True,
                                       help_text='Show on the public site. Untick for evidence that only staff should see.')
    order        = models.PositiveSmallIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    objects = AttachmentQuerySet.as_manager()
    history = HistoricalRecords()

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [models.Index(fields=['content_type', 'object_id'], name='attachment_record_idx')]
        verbose_name = 'Photo / Evidence'
        verbose_name_plural = 'Photos & Evidence'

    def __str__(self):
        return self.title or self.get_kind_display()

    def clean(self):
        super().clean()
        if not self.file and not self.external_url:
            raise ValidationError('Upload a file or give a link.')

    @property
    def extension(self):
        return extension_of(self.file.name) if self.file else ''

    @property
    def is_image(self):
        return self.extension in IMAGE_EXTENSIONS

    @property
    def is_audio(self):
        return self.extension in AUDIO_EXTENSIONS

    @property
    def is_video(self):
        return self.extension in VIDEO_EXTENSIONS


def record_is_public(obj):
    """True when `obj` (any archive record) may be seen by the public."""
    if obj is None or getattr(obj, 'is_deleted', False):
        return False
    qs = type(obj)._default_manager.all()
    if hasattr(qs, 'public'):
        return qs.public().filter(pk=obj.pk).exists()
    clan = getattr(obj, 'clan', None)  # chiefs, events, bomas, landmarks follow their clan
    if clan is not None:
        return clan.is_public
    return False
