from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from apps.core.models import PAYAM_CHOICES


class Clan(models.Model):
    name                 = models.CharField(max_length=200, unique=True)
    slug                 = models.SlugField(max_length=220, unique=True, blank=True)
    payam                = models.CharField(max_length=50, choices=PAYAM_CHOICES)
    tagline              = models.CharField(max_length=300, blank=True)
    description          = models.TextField(help_text='General overview')
    origin_story         = models.TextField(blank=True)
    migration_history    = models.TextField(blank=True)
    territorial_notes    = models.TextField(blank=True)
    cultural_practices   = models.TextField(blank=True)
    traditional_beliefs  = models.TextField(blank=True)
    historical_events    = models.TextField(blank=True)

    # ── GEOGRAPHY ──
    population_estimate  = models.CharField(max_length=100, blank=True, help_text='Estimated current population')
    border_north         = models.CharField(max_length=400, blank=True, help_text='Northern border: neighbouring community or landmark')
    border_south         = models.CharField(max_length=400, blank=True, help_text='Southern border')
    border_east          = models.CharField(max_length=400, blank=True, help_text='Eastern border')
    border_west          = models.CharField(max_length=400, blank=True, help_text='Western border')
    rivers               = models.TextField(blank=True, help_text='Rivers, streams, and water bodies in clan territory')
    landscape            = models.TextField(blank=True, help_text='Description of the landscape, terrain, and natural features')

    # ── LIVELIHOOD ──
    main_activities      = models.TextField(blank=True, help_text='Main economic activities: farming, fishing, cattle-keeping, trade, etc.')
    infrastructure       = models.TextField(blank=True, help_text='Schools, health facilities, roads, churches, markets')

    # ── RELATED ──
    allied_clans         = models.ManyToManyField('self', blank=True, symmetrical=True)
    sub_clans            = models.TextField(blank=True, help_text='Known sub-clans (comma-separated)')

    # ── STATUS ──
    is_verified          = models.BooleanField(default=False)
    is_featured          = models.BooleanField(default=False)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self): return f'{self.name} Clan'
    def get_absolute_url(self): return reverse('clans:detail', kwargs={'slug': self.slug})

    @property
    def person_count(self): return self.person_set.filter(is_verified=True).count()

    @property
    def family_count(self): return self.family_set.filter(is_verified=True).count()

    @property
    def sub_clan_list(self): return [s.strip() for s in self.sub_clans.split(',') if s.strip()]


class ClanChief(models.Model):
    clan       = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='chiefs')
    name       = models.CharField(max_length=200)
    title      = models.CharField(max_length=100, default='Chief')
    start_year = models.CharField(max_length=10, blank=True)
    end_year   = models.CharField(max_length=10, blank=True)
    notes      = models.TextField(blank=True)
    photo      = models.ImageField(upload_to='clans/chiefs/', blank=True, null=True)
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'start_year']
        verbose_name = 'Chief / Elder'

    def __str__(self): return f'{self.title} {self.name} — {self.clan.name}'

    @property
    def tenure(self):
        if self.start_year and self.end_year: return f'{self.start_year} – {self.end_year}'
        if self.start_year: return f'{self.start_year} – present'
        return ''


class ClanEvent(models.Model):
    clan         = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='events')
    title        = models.CharField(max_length=300)
    year         = models.CharField(max_length=20, blank=True)
    description  = models.TextField()
    significance = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['year']
        verbose_name = 'Historical Event'

    def __str__(self): return f'{self.title} ({self.year})'


class ClanBoma(models.Model):
    """A boma is a sub-territorial unit within a clan's land."""
    clan              = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='bomas')
    name              = models.CharField(max_length=200, help_text='Name of the boma')
    history           = models.TextField(help_text='History and background of this boma')
    current_leader    = models.CharField(max_length=200, blank=True, help_text='Current payam/boma administrator or chief')
    past_leaders      = models.TextField(blank=True, help_text='Names of past leaders with their approximate years')
    population        = models.CharField(max_length=100, blank=True, help_text='Estimated population of this boma')
    main_activities   = models.TextField(blank=True, help_text='Main economic activities of people in this boma')
    location_description = models.TextField(blank=True, help_text='Location, borders, and landmarks')
    year_established  = models.CharField(max_length=20, blank=True)
    infrastructure    = models.TextField(blank=True, help_text='Schools, health facilities, churches, markets in this boma')
    notable_persons   = models.TextField(blank=True, help_text='Notable people from this boma')
    notes             = models.TextField(blank=True)
    order             = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Boma'

    def __str__(self): return f'{self.name} — {self.clan.name} Clan'


CLAN_SECTION_CHOICES = [
    ('general',       'General'),
    ('history',       'Historical'),
    ('geography',     'Geography & Landscape'),
    ('rivers',        'Rivers & Water'),
    ('boma',          'Boma'),
    ('leaders',       'Leadership'),
    ('culture',       'Cultural'),
    ('community',     'Community Life'),
    ('infrastructure','Infrastructure'),
    ('events',        'Events & Celebrations'),
    ('achievements',  'Achievements'),
]


class ClanMedia(models.Model):
    MEDIA_TYPES = [
        ('photo',    'Photo'),
        ('document', 'Document / PDF'),
        ('video',    'Video'),
        ('audio',    'Audio Recording'),
    ]
    clan       = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='media_files')
    boma       = models.ForeignKey(ClanBoma, on_delete=models.SET_NULL, null=True, blank=True, related_name='media', help_text='Link to a specific boma if this media is boma-specific')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES, default='photo')
    section    = models.CharField(max_length=30, choices=CLAN_SECTION_CHOICES, default='general', help_text='Which section of the clan page this media belongs to')
    title      = models.CharField(max_length=300)
    file       = models.FileField(upload_to='clans/media/', blank=True, null=True)
    video_url  = models.URLField(blank=True, help_text='YouTube/Vimeo link')
    caption    = models.TextField(blank=True)
    date_taken = models.CharField(max_length=100, blank=True, help_text='Date or approximate year')
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['section', 'order']
        verbose_name = 'Clan Media'

    def __str__(self): return f'{self.get_media_type_display()}: {self.title} ({self.clan.name})'