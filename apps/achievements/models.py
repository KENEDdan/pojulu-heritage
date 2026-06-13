from django.db import models
from django.urls import reverse


CATEGORY_CHOICES = [
    ('leadership',  'Leadership & Governance'),
    ('education',   'Education & Academia'),
    ('culture',     'Culture & Arts'),
    ('service',     'Community Service'),
    ('sport',       'Sport & Athletics'),
    ('business',    'Business & Enterprise'),
    ('religion',    'Faith & Religion'),
    ('military',    'Military & Security'),
    ('other',       'Other'),
]

CATEGORY_ICONS = {
    'leadership': '🏛️',
    'education':  '🎓',
    'culture':    '🎭',
    'service':    '❤️',
    'sport':      '⚽',
    'business':   '💼',
    'religion':   '✝️',
    'military':   '🎖️',
    'other':      '⭐',
}


class Achievement(models.Model):
    person_name  = models.CharField(max_length=200,
                                     help_text="Full name of the person being honoured")
    person       = models.ForeignKey('genealogy.Person', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='achievements',
                                      help_text="Link to person record if they exist in the archive")
    clan         = models.ForeignKey('clans.Clan', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='achievements')
    category     = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title        = models.CharField(max_length=500, help_text="One-line achievement title")
    description  = models.TextField()
    year         = models.CharField(max_length=10, blank=True)
    source       = models.CharField(max_length=300, blank=True,
                                     help_text="Source / reference for this achievement")
    is_verified  = models.BooleanField(default=False)
    is_featured  = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', 'person_name']
        verbose_name = 'Achievement'

    def __str__(self):
        return f"{self.person_name} — {self.title[:60]}"

    def get_absolute_url(self):
        return reverse('achievements:detail', kwargs={'pk': self.pk})

    @property
    def icon(self):
        return CATEGORY_ICONS.get(self.category, '⭐')

    @property
    def category_label(self):
        return dict(CATEGORY_CHOICES).get(self.category, self.category)
