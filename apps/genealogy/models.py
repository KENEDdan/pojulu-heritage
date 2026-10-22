from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from apps.core.models import PAYAM_CHOICES
from apps.core.storage import get_private_storage
from apps.core.uploads import SafeFileField, SafeImageField, UploadTo
from apps.core.validators import validate_document_or_image, validate_image, validate_media, validate_pdf

GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('U', 'Unknown')]


class FamilyQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_verified=True)


class PersonQuerySet(models.QuerySet):
    def public(self):
        """Visible on the public site: verified, and not a living person
        who asked to be private."""
        return self.filter(is_verified=True).exclude(is_private=True, is_deceased=False)


class Family(models.Model):
    name           = models.CharField(max_length=200)
    slug           = models.SlugField(max_length=220, unique=True, blank=True)
    clan           = models.ForeignKey('clans.Clan', on_delete=models.SET_NULL, null=True, blank=True, related_name='family_set')
    payam          = models.CharField(max_length=50, choices=PAYAM_CHOICES, blank=True)
    origin_village = models.CharField(max_length=200, blank=True)
    description    = models.TextField(blank=True)
    is_verified    = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    objects = FamilyQuerySet.as_manager()

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name); slug = base; n = 1
            while Family.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return self.name
    def get_absolute_url(self): return reverse('genealogy:family_detail', kwargs={'slug': self.slug})

    @property
    def member_count(self): return self.person_set.public().count()

    @property
    def head(self): return self.person_set.public().filter(father__isnull=True).first()


class Person(models.Model):
    # ── IDENTITY ──
    first_name   = models.CharField(max_length=100)
    middle_name  = models.CharField(max_length=100, blank=True)
    last_name    = models.CharField(max_length=200)
    other_names  = models.CharField(max_length=200, blank=True, help_text='Traditional or other known names')
    slug         = models.SlugField(max_length=300, unique=True, blank=True)
    gender       = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U')

    # ── HERITAGE ──
    clan         = models.ForeignKey('clans.Clan', on_delete=models.SET_NULL, null=True, blank=True, related_name='person_set')
    family       = models.ForeignKey(Family, on_delete=models.SET_NULL, null=True, blank=True, related_name='person_set')
    payam        = models.CharField(max_length=50, choices=PAYAM_CHOICES, blank=True)

    # ── PARENTAGE ──
    father       = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children_father', verbose_name='Father')
    mother       = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children_mother', verbose_name='Mother')

    # ── BIRTH & DEATH ──
    birth_year   = models.CharField(max_length=20, blank=True)
    birth_date   = models.DateField(null=True, blank=True)
    birth_place  = models.CharField(max_length=300, blank=True)
    is_deceased  = models.BooleanField(default=False)
    death_year   = models.CharField(max_length=20, blank=True)
    death_date   = models.DateField(null=True, blank=True)
    death_place  = models.CharField(max_length=300, blank=True)

    # ── CONTACT & LOCATION ──
    phone            = models.CharField(max_length=80, blank=True, help_text='Phone number (optional)')
    email_contact    = models.EmailField(blank=True, help_text='Contact email (optional)')
    address          = models.TextField(blank=True, help_text='Current physical address')
    current_residence = models.CharField(max_length=300, blank=True)

    # ── PROFILE ──
    photo            = SafeImageField(upload_to=UploadTo('persons/photos'), blank=True, null=True,
                                      validators=[validate_image])
    biography        = models.TextField(blank=True)
    occupation       = models.CharField(max_length=300, blank=True)
    hobbies          = models.TextField(blank=True, help_text='Hobbies and personal interests')
    skills_talents   = models.TextField(blank=True, help_text='Skills, talents, and gifts')
    languages_spoken = models.CharField(max_length=300, blank=True, help_text='e.g. Pojulu, Arabic, English')
    religion         = models.CharField(max_length=100, blank=True)
    contributions    = models.TextField(blank=True, help_text='Community contributions and service')

    # ── DOCUMENTS ──
    profile_pdf      = SafeFileField(upload_to=UploadTo('persons/pdfs'), blank=True, null=True,
                                     storage=get_private_storage,
                                     help_text='Upload full profile PDF document (max 25 MB). Staff-only.',
                                     validators=[validate_pdf])

    # ── PRIVACY ──
    show_contact_publicly = models.BooleanField(
        default=False,
        help_text='Show phone, email and address on the public profile. Only tick this with the person\'s consent.')
    is_private   = models.BooleanField(
        default=False,
        help_text='Hide this living person from public pages, search, lists and family trees.')

    # ── META ──
    is_verified  = models.BooleanField(default=False)
    is_elder     = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    submitted_by = models.CharField(max_length=200, blank=True)

    objects = PersonQuerySet.as_manager()

    class Meta:
        ordering = ['last_name', 'first_name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.first_name} {self.last_name}')
            slug, n = base, 1
            while Person.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'; n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self): return self.full_name
    def get_absolute_url(self): return reverse('genealogy:person_detail', kwargs={'slug': self.slug})

    @property
    def full_name(self):
        return ' '.join(p for p in [self.first_name, self.middle_name, self.last_name] if p)

    @property
    def initials(self):
        return ''.join(p[0].upper() for p in self.full_name.split()[:2])

    @property
    def lifespan(self):
        if self.birth_year and self.death_year: return f'{self.birth_year} – {self.death_year}'
        if self.birth_year and self.is_deceased: return f'{self.birth_year} – ?'
        if self.birth_year: return f'b. {self.birth_year}'
        return ''

    @property
    def siblings(self):
        qs = Person.objects.none()
        if self.father: qs = qs | self.father.children_father.exclude(pk=self.pk)
        if self.mother: qs = qs | self.mother.children_mother.exclude(pk=self.pk)
        return qs.distinct()

    @property
    def spouses(self):
        from apps.marriages.models import Marriage
        spouses = []
        for m in Marriage.objects.filter(husband=self).select_related('wife'):
            if m.wife: spouses.append(m.wife)
        for m in Marriage.objects.filter(wife=self).select_related('husband'):
            if m.husband: spouses.append(m.husband)
        return spouses

    @property
    def children(self):
        return Person.objects.filter(
            models.Q(father=self) | models.Q(mother=self)
        ).distinct()

    @property
    def is_public(self):
        return self.is_verified and not (self.is_private and not self.is_deceased)

    @property
    def public_contact(self):
        """Contact details for public templates — empty unless the person
        consented (show_contact_publicly)."""
        if not self.show_contact_publicly or self.is_deceased:
            return {}
        return {k: v for k, v in (('phone', self.phone), ('email', self.email_contact),
                                  ('address', self.address)) if v}

    def public_relatives(self):
        """Parents, spouses, children and siblings filtered to publicly
        visible people (the unfiltered properties above are for staff/wills)."""
        public = Person.objects.public()
        parent_ids = [i for i in (self.father_id, self.mother_id) if i]
        parents = {p.pk: p for p in public.filter(pk__in=parent_ids)}
        spouse_ids = [s.pk for s in self.spouses]
        return {
            'father': parents.get(self.father_id),
            'mother': parents.get(self.mother_id),
            'spouses': list(public.filter(pk__in=spouse_ids)),
            'children': list(self.children.public()),
            'siblings': list(self.siblings.public()),
        }


class PersonEducation(models.Model):
    person       = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='education_history')
    institution  = models.CharField(max_length=300, help_text='School, college, or university name')
    qualification = models.CharField(max_length=300, help_text='e.g. Bachelor of Arts, KCSE Certificate')
    field_of_study = models.CharField(max_length=300, blank=True, help_text='Subject or discipline')
    start_year   = models.CharField(max_length=10, blank=True)
    end_year     = models.CharField(max_length=10, blank=True)
    is_current   = models.BooleanField(default=False, help_text='Currently studying here')
    honors       = models.CharField(max_length=200, blank=True, help_text='e.g. First Class, Distinction')
    notes        = models.TextField(blank=True)
    certificate  = SafeFileField(upload_to=UploadTo('persons/education'), blank=True, null=True,
                                 storage=get_private_storage,
                                 help_text='Upload certificate or transcript (PDF/JPG)',
                                 validators=[validate_document_or_image], image_max_edge=2400)
    order        = models.PositiveSmallIntegerField(default=0, help_text='Display order (0 = most recent)')

    class Meta:
        ordering = ['order', '-start_year']
        verbose_name = 'Education Record'

    def __str__(self):
        return f'{self.qualification} — {self.institution}'

    @property
    def period(self):
        if self.start_year and self.end_year: return f'{self.start_year}–{self.end_year}'
        if self.start_year and self.is_current: return f'{self.start_year}–Present'
        return self.start_year or ''


class PersonCareer(models.Model):
    person      = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='career_history')
    employer    = models.CharField(max_length=300, help_text='Organisation or employer name')
    position    = models.CharField(max_length=300, help_text='Job title or role')
    location    = models.CharField(max_length=300, blank=True)
    start_year  = models.CharField(max_length=10, blank=True)
    end_year    = models.CharField(max_length=10, blank=True)
    is_current  = models.BooleanField(default=False, help_text='Currently working here')
    description = models.TextField(blank=True, help_text='Responsibilities, achievements, and contributions in this role')
    order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', '-start_year']
        verbose_name = 'Career Record'

    def __str__(self):
        return f'{self.position} at {self.employer}'

    @property
    def period(self):
        if self.start_year and self.end_year: return f'{self.start_year}–{self.end_year}'
        if self.start_year and self.is_current: return f'{self.start_year}–Present'
        return self.start_year or ''


class PersonMedia(models.Model):
    MEDIA_TYPES = [
        ('photo',    'Photo'),
        ('document', 'Document / PDF'),
        ('video',    'Video'),
        ('audio',    'Audio Recording'),
    ]
    person          = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='media_files')
    media_type      = models.CharField(max_length=20, choices=MEDIA_TYPES, default='photo')
    title           = models.CharField(max_length=300, blank=True)
    file            = SafeFileField(upload_to=UploadTo('persons/media'), storage=get_private_storage,
                                    help_text='Photo, PDF, audio, or video file (staff-only)',
                                    validators=[validate_media])
    video_url       = models.URLField(blank=True, help_text='YouTube/Vimeo link (alternative to file upload)')
    caption         = models.TextField(blank=True)
    date_taken      = models.CharField(max_length=100, blank=True, help_text='Date or approximate year')
    is_profile_photo = models.BooleanField(default=False, help_text='Use as main profile photo')
    order           = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'media_type']
        verbose_name = 'Person Media'

    def __str__(self):
        return f'{self.get_media_type_display()}: {self.title or self.person.full_name}'