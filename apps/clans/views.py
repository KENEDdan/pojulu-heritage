# apps/clans/views.py
from django.conf import settings
from apps.core.utils import search_term
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Clan

class ClanListView(ListView):
    model = Clan
    template_name = 'clans/list.html'
    context_object_name = 'clans'
    paginate_by = settings.RECORDS_PER_PAGE

    def get_queryset(self):
        qs = Clan.objects.public().with_counts().prefetch_related('chiefs').order_by('name')
        q = search_term(self.request)
        payam = self.request.GET.get('payam', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if payam:
            qs = qs.filter(payam=payam)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = search_term(self.request)
        ctx['selected_payam'] = self.request.GET.get('payam', '')
        ctx['payam_choices'] = [('rokon','Rokon'),('tijor','Tijor'),('dolo','Dolo'),('juba','Juba County')]
        ctx['total_count'] = ctx['paginator'].count if ctx.get('paginator') else len(ctx['clans'])
        return ctx

class ClanDetailView(DetailView):
    model = Clan
    template_name = 'clans/detail.html'
    context_object_name = 'clan'
    queryset = Clan.objects.public()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        clan = self.object
        ctx['chiefs'] = clan.chiefs.all().order_by('order')
        ctx['events'] = clan.events.all()
        ctx['families'] = clan.family_set.public().with_counts().select_related('clan').order_by('name')[:10]
        ctx['persons'] = clan.person_set.public().select_related('clan').order_by('last_name')[:12]
        ctx['achievements'] = clan.achievements.public()[:5]
        ctx['marriages'] = clan.marriages_husband_clan.public()[:5]
        ctx['interviews'] = clan.elderinterview_set.public()[:3]
        ctx['cultural_records'] = clan.culturalrecord_set.public()[:5]
        return ctx
