import json

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords
from apps.core.softdelete import SoftDeleteModel, soft_delete_managers
from apps.core.embeds import validate_video_url
from django.urls import reverse
from django.utils.text import slugify
from apps.core.models import PAYAM_CHOICES
from apps.core.uploads import SafeFileField, SafeImageField, UploadTo
from apps.core.validators import validate_image, validate_media


MAX_BOUNDARY_BYTES = 200_000


def _check_ring(ring):
    if not isinstance(ring, list) or len(ring) < 4:
        raise ValidationError('Each boundary needs at least three points.')
    for pt in ring:
        if (not isinstance(pt, list) or len(pt) < 2
                or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in pt[:2])):
            raise ValidationError('Boundary points must be [longitude, latitude] numbers.')
        lng, lat = pt[0], pt[1]
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise ValidationError('A boundary point is outside the valid latitude/longitude range.')


def validate_boundary_geojson(value):
    """Accept a GeoJSON Polygon / MultiPolygon (bare, Feature or
    FeatureCollection) and nothing else."""
    if not value:
        return
    if len(value.encode()) > MAX_BOUNDARY_BYTES:
        raise ValidationError('The boundary is too detailed (over 200 KB). Simplify it.')
    try:
        data = json.loads(value)
    except ValueError:
        raise ValidationError('The boundary is not valid GeoJSON.')
    if isinstance(data, dict) and data.get('type') == 'FeatureCollection':
        geoms = [f.get('geometry') for f in data.get('features') or [] if isinstance(f, dict)]
    elif isinstance(data, dict) and data.get('type') == 'Feature':
        geoms = [data.get('geometry')]
    else:
        geoms = [data]
    if not geoms:
        raise ValidationError('The boundary is empty.')
    for g in geoms:
        if not isinstance(g, dict) or g.get('type') not in ('Polygon', 'MultiPolygon'):
            raise ValidationError('The boundary must be a polygon.')
        polygons = [g.get('coordinates')] if g['type'] == 'Polygon' else g.get('coordinates')
        if not isinstance(polygons, list) or not polygons:
            raise ValidationError('The boundary has no coordinates.')
        for poly in polygons:
            if not isinstance(poly, list) or not poly:
                raise ValidationError('The boundary has no coordinates.')
            for ring in poly:
                _check_ring(ring)


class ClanQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_verified=True)

    def with_counts(self):
        """Annotate public person/family counts in the same query (used by
        Clan.person_count / family_count instead of one query per clan)."""
        visible = (models.Q(person_set__is_verified=True, person_set__is_deleted=False)
                   & ~models.Q(person_set__is_private=True, person_set__is_deceased=False))
        return self.annotate(
            n_persons=models.Count('person_set', filter=visible, distinct=True),
            n_families=models.Count('family_set', distinct=True,
                                    filter=models.Q(family_set__is_verified=True, family_set__is_deleted=False)),
        )


class Clan(SoftDeleteModel):
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

    # ── TERRITORY & MAP ──
    territory_description = models.TextField(blank=True, help_text="Full written account of the clan's land: where it starts and ends, how it was acquired, disputes and changes over time")
    area_estimate        = models.CharField(max_length=100, blank=True, help_text='Approximate size, e.g. "about 120 km²"')
    map_image            = SafeImageField(upload_to=UploadTo('clans/maps'), blank=True, null=True,
                                          validators=[validate_image], image_max_edge=2400,
                                          help_text='A scanned or hand-drawn map of the territory (optional)')
    boundary_geojson     = models.TextField(blank=True, validators=[validate_boundary_geojson],
                                            help_text='Boundary drawn on the map (filled in by the map editor)')

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

    objects, all_objects = soft_delete_managers(ClanQuerySet)
    history = HistoricalRecords()
    attachments = GenericRelation('core.Attachment')

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self): return f'{self.name} Clan'

    def clean(self):
        super().clean()
        # The default manager hides the Trash, so Django's own unique check
        # would miss a deleted clan with the same name and the save would fail.
        if self.name and Clan.all_objects.filter(name__iexact=self.name, is_deleted=True).exclude(pk=self.pk).exists():
            raise ValidationError({'name': 'A clan with this name is in the Trash. Restore it instead of creating a new one.'})

    @property
    def is_public(self): return self.is_verified and not self.is_deleted
    def get_absolute_url(self): return reverse('clans:detail', kwargs={'slug': self.slug})

    @property
    def person_count(self):
        if 'n_persons' in self.__dict__:
            return self.n_persons
        return self.person_set.public().count()

    @property
    def family_count(self):
        if 'n_families' in self.__dict__:
            return self.n_families
        return self.family_set.public().count()

    @property
    def sub_clan_list(self): return [s.strip() for s in self.sub_clans.split(',') if s.strip()]


class ClanChief(models.Model):
    clan       = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='chiefs')
    person     = models.ForeignKey('genealogy.Person', null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='chief_roles',
                                   help_text="Link to this chief's person record, if they have one")
    name       = models.CharField(max_length=200)
    other_names = models.CharField(max_length=200, blank=True, help_text='Traditional names or titles they were known by')
    title      = models.CharField(max_length=100, default='Chief')
    start_year = models.CharField(max_length=10, blank=True)
    end_year   = models.CharField(max_length=10, blank=True)
    birth_year = models.CharField(max_length=20, blank=True)
    death_year = models.CharField(max_length=20, blank=True)
    burial_place = models.CharField(max_length=300, blank=True)
    summary    = models.CharField(max_length=400, blank=True, help_text='One or two sentences shown on the clan page')
    how_appointed = models.TextField(blank=True, help_text='How they became chief: inheritance, election or appointment, and by whom')
    biography  = models.TextField(blank=True, help_text='Full life story: early life, family, character')
    accomplishments = models.TextField(blank=True, help_text='What they did as chief: disputes settled, land defended, schools, roads, churches, reforms')
    major_events = models.TextField(blank=True, help_text='Wars, famines, migrations, visits and other events during their rule')
    challenges = models.TextField(blank=True, help_text='Difficulties and controversies')
    legacy     = models.TextField(blank=True, help_text='How they are remembered today')
    sources    = models.TextField(blank=True, help_text='Who told this history, and documents consulted')
    notes      = models.TextField(blank=True)
    photo      = SafeImageField(upload_to=UploadTo('clans/chiefs'), blank=True, null=True,
                                validators=[validate_image])
    order      = models.PositiveSmallIntegerField(default=0)

    history = HistoricalRecords()
    attachments = GenericRelation('core.Attachment')

    class Meta:
        ordering = ['order', 'start_year']
        verbose_name = 'Chief / Elder'

    def __str__(self): return f'{self.title} {self.name} — {self.clan.name}'

    def get_absolute_url(self):
        return reverse('clans:chief_detail', kwargs={'slug': self.clan.slug, 'pk': self.pk})

    @property
    def lifespan(self):
        if self.birth_year and self.death_year: return f'{self.birth_year} – {self.death_year}'
        if self.birth_year: return f'b. {self.birth_year}'
        if self.death_year: return f'd. {self.death_year}'
        return ''

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

    history = HistoricalRecords()
    attachments = GenericRelation('core.Attachment')

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

    # `history` is already a data field on bomas, so the audit trail uses another name.
    change_history = HistoricalRecords()
    attachments = GenericRelation('core.Attachment')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Boma'

    def __str__(self): return f'{self.name} — {self.clan.name} Clan'


LANDMARK_TYPES = [
    ('hill',     'Hill / mountain'),
    ('rock',     'Rock / cave'),
    ('river',    'River / stream / spring'),
    ('forest',   'Forest / grove'),
    ('tree',     'Notable tree'),
    ('sacred',   'Sacred site / shrine'),
    ('burial',   'Burial ground'),
    ('battle',   'Battle or historic site'),
    ('boundary', 'Boundary marker'),
    ('market',   'Market'),
    ('school',   'School'),
    ('church',   'Church / place of worship'),
    ('health',   'Health facility'),
    ('other',    'Other'),
]


class ClanLandmark(models.Model):
    clan         = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='landmarks')
    name         = models.CharField(max_length=200)
    landmark_type = models.CharField(max_length=20, choices=LANDMARK_TYPES, default='other')
    description  = models.TextField(help_text='What it is and where')
    history      = models.TextField(blank=True, help_text='Its story and significance to the clan')
    location_description = models.CharField(max_length=400, blank=True,
                                            help_text='How to find it, e.g. "2 km east of Kupera market"')
    latitude     = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude    = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    show_on_public_map = models.BooleanField(
        default=True,
        help_text='Untick to keep the exact spot private (recommended for shrines, sacred sites and '
                  'burial grounds). Staff still see it; the public page shows the description only.')
    photo        = SafeImageField(upload_to=UploadTo('clans/landmarks'), blank=True, null=True,
                                  validators=[validate_image],
                                  help_text='Main photo (add more under Photos & Evidence)')
    order        = models.PositiveSmallIntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    # `history` is a data field here too, so the audit trail uses another name.
    change_history = HistoricalRecords()
    attachments = GenericRelation('core.Attachment')

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Landmark'

    def __str__(self): return f'{self.name} — {self.clan.name} Clan'

    def clean(self):
        super().clean()
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError('Give both latitude and longitude, or neither (click the map to place it).')
        if self.latitude is not None and not (-90 <= self.latitude <= 90):
            raise ValidationError({'latitude': 'Latitude must be between -90 and 90.'})
        if self.longitude is not None and not (-180 <= self.longitude <= 180):
            raise ValidationError({'longitude': 'Longitude must be between -180 and 180.'})

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def has_public_location(self):
        return self.has_location and self.show_on_public_map


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
    file       = SafeFileField(upload_to=UploadTo('clans/media'), blank=True, null=True,
                               validators=[validate_media])
    video_url  = models.URLField(blank=True, validators=[validate_video_url], help_text='YouTube/Vimeo link')
    caption    = models.TextField(blank=True)
    date_taken = models.CharField(max_length=100, blank=True, help_text='Date or approximate year')
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['section', 'order']
        verbose_name = 'Clan Media'

    def __str__(self): return f'{self.get_media_type_display()}: {self.title} ({self.clan.name})'