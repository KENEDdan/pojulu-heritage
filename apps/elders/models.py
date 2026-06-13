from django.db import models
from django.urls import reverse


class ElderInterview(models.Model):
    elder_name      = models.CharField(max_length=200)
    elder_person    = models.ForeignKey('genealogy.Person', null=True, blank=True,
                                         on_delete=models.SET_NULL,
                                         help_text="Link to person record if they exist in archive")
    clan            = models.ForeignKey('clans.Clan', null=True, blank=True,
                                         on_delete=models.SET_NULL)
    payam           = models.CharField(max_length=100, blank=True)
    approximate_age = models.PositiveSmallIntegerField(null=True, blank=True)
    interview_date  = models.DateField(null=True, blank=True)
    interview_location = models.CharField(max_length=200, blank=True)
    interviewer     = models.CharField(max_length=200)
    language        = models.CharField(max_length=100, default='Pojulu / English')

    summary         = models.TextField(help_text="Summary of topics covered and key information shared")
    transcript      = models.TextField(blank=True,
                                        help_text="Full transcript of the interview")
    topics_covered  = models.CharField(max_length=600, blank=True,
                                        help_text="Comma-separated list of topics covered")

    audio_file      = models.FileField(upload_to='interviews/audio/', blank=True, null=True)
    video_file      = models.FileField(upload_to='interviews/video/', blank=True, null=True)
    video_url       = models.URLField(blank=True, help_text="External video link")
    photo_of_elder  = models.ImageField(upload_to='interviews/photos/', blank=True, null=True)

    clans_mentioned    = models.ManyToManyField('clans.Clan', blank=True,
                                                 related_name='mentioned_in_interviews')
    is_published    = models.BooleanField(default=False,
                                           help_text="Only published interviews appear on the site")
    is_featured     = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-interview_date', 'elder_name']
        verbose_name = 'Elder Interview'

    def __str__(self):
        date = self.interview_date.strftime('%b %Y') if self.interview_date else 'undated'
        return f"Interview: {self.elder_name} ({date})"

    def get_absolute_url(self):
        return reverse('elders:detail', kwargs={'pk': self.pk})

    @property
    def topics_list(self):
        return [t.strip() for t in self.topics_covered.split(',') if t.strip()]

    @property
    def has_audio(self):
        return bool(self.audio_file)

    @property
    def has_video(self):
        return bool(self.video_file) or bool(self.video_url)

    @property
    def has_transcript(self):
        return bool(self.transcript.strip())

    @property
    def initials(self):
        parts = self.elder_name.split()
        return ''.join(p[0].upper() for p in parts[:2])
