from django.db import models
from django.urls import reverse


class Marriage(models.Model):
    husband           = models.ForeignKey('genealogy.Person', null=True, blank=True,
                                           on_delete=models.SET_NULL,
                                           related_name='marriages_as_husband')
    husband_name      = models.CharField(max_length=200, blank=True,
                                          help_text="If husband not in archive")
    husband_clan      = models.ForeignKey('clans.Clan', null=True, blank=True,
                                           on_delete=models.SET_NULL,
                                           related_name='marriages_husband_clan')
    husband_community = models.CharField(max_length=200, blank=True,
                                          help_text="If from outside the Pojulu community")

    wife              = models.ForeignKey('genealogy.Person', null=True, blank=True,
                                           on_delete=models.SET_NULL,
                                           related_name='marriages_as_wife')
    wife_name         = models.CharField(max_length=200, blank=True,
                                          help_text="If wife not in archive")
    wife_clan         = models.ForeignKey('clans.Clan', null=True, blank=True,
                                           on_delete=models.SET_NULL,
                                           related_name='marriages_wife_clan')
    wife_community    = models.CharField(max_length=200, blank=True,
                                          help_text="If from outside the Pojulu community")

    year              = models.CharField(max_length=10, blank=True)
    place             = models.CharField(max_length=300, blank=True)
    payam             = models.CharField(max_length=100, blank=True)
    notes             = models.TextField(blank=True)
    children_names    = models.TextField(blank=True,
                                          help_text="Names of children from this union")
    is_verified       = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year']
        verbose_name = 'Marriage Record'

    def __str__(self):
        h = self.husband.full_name if self.husband else self.husband_name
        w = self.wife.full_name    if self.wife    else self.wife_name
        return f"{h} & {w} ({self.year})"

    def get_absolute_url(self):
        return reverse('marriages:detail', kwargs={'pk': self.pk})

    @property
    def husband_display(self):
        return self.husband.full_name if self.husband else self.husband_name

    @property
    def wife_display(self):
        return self.wife.full_name if self.wife else self.wife_name

    @property
    def husband_clan_display(self):
        if self.husband and self.husband.clan:
            return str(self.husband.clan)
        if self.husband_clan:
            return str(self.husband_clan)
        return self.husband_community or '—'

    @property
    def wife_clan_display(self):
        if self.wife and self.wife.clan:
            return str(self.wife.clan)
        if self.wife_clan:
            return str(self.wife_clan)
        return self.wife_community or '—'

    @property
    def children_list(self):
        return [c.strip() for c in self.children_names.split(',') if c.strip()]
