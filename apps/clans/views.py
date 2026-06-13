# apps/clans/views.py
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Clan

class ClanListView(ListView):
    model = Clan
    template_name = 'clans/list.html'
    context_object_name = 'clans'
    paginate_by = 12

    def get_queryset(self):
        qs = Clan.objects.filter(is_verified=True).prefetch_related('chiefs')
        q = self.request.GET.get('q', '')
        payam = self.request.GET.get('payam', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if payam:
            qs = qs.filter(payam=payam)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q', '')
        ctx['selected_payam'] = self.request.GET.get('payam', '')
        ctx['payam_choices'] = [('rokon','Rokon'),('tijor','Tijor'),('dolo','Dolo'),('juba','Juba County')]
        ctx['total_count'] = self.get_queryset().count()
        return ctx

class ClanDetailView(DetailView):
    model = Clan
    template_name = 'clans/detail.html'
    context_object_name = 'clan'
    queryset = Clan.objects.filter(is_verified=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        clan = self.object
        ctx['chiefs'] = clan.chiefs.all().order_by('order')
        ctx['events'] = clan.events.all()
        ctx['families'] = clan.family_set.filter(is_verified=True)[:10]
        ctx['persons'] = clan.person_set.filter(is_verified=True).order_by('last_name')[:12]
        ctx['achievements'] = clan.achievements.filter(is_verified=True)[:5]
        ctx['marriages'] = clan.marriages_husband_clan.filter(is_verified=True)[:5]
        ctx['interviews'] = clan.elderinterview_set.filter(is_published=True)[:3]
        ctx['cultural_records'] = clan.culturalrecord_set.filter(is_verified=True)[:5]
        return ctx
