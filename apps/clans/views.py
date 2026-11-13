# apps/clans/views.py
from django.conf import settings
from apps.core.utils import search_term
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q


from .models import Clan, ClanChief

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
        ctx['chiefs'] = clan.chiefs.all().order_by('order', 'start_year')
        ctx['events'] = clan.events.all()
        ctx['landmarks'] = list(clan.landmarks.prefetch_related('attachments'))
        ctx['bomas'] = clan.bomas.all()
        ctx['gallery'] = clan.media_files.all()
        ctx['evidence'] = clan.attachments.public()
        ctx['map_data'] = {
            'boundary': clan.boundary_geojson or None,
            'landmarks': [{'name': lm.name, 'type': lm.get_landmark_type_display(),
                           'lat': float(lm.latitude), 'lng': float(lm.longitude)}
                          for lm in ctx['landmarks'] if lm.has_location],
        }
        ctx['has_map'] = bool(clan.boundary_geojson or ctx['map_data']['landmarks'])
        ctx['has_territory'] = ctx['has_map'] or any([
            clan.territory_description, clan.map_image, clan.border_north, clan.border_south,
            clan.border_east, clan.border_west, clan.rivers, clan.landscape, clan.area_estimate, ctx['bomas']])
        ctx['families'] = clan.family_set.public().with_counts().select_related('clan').order_by('name')[:10]
        ctx['persons'] = clan.person_set.public().select_related('clan').order_by('last_name')[:12]
        ctx['achievements'] = clan.achievements.public()[:5]
        ctx['marriages'] = clan.marriages_husband_clan.public()[:5]
        ctx['interviews'] = clan.elderinterview_set.public()[:3]
        ctx['cultural_records'] = clan.culturalrecord_set.public()[:5]
        return ctx


def chief_detail(request, slug, pk):
    clan = get_object_or_404(Clan.objects.public(), slug=slug)
    chief = get_object_or_404(ClanChief.objects.select_related('person'), pk=pk, clan=clan)
    line = list(clan.chiefs.order_by('order', 'start_year'))
    i = line.index(chief)
    person = chief.person if chief.person and chief.person.is_public and not chief.person.is_deleted else None
    return render(request, 'clans/chief_detail.html', {
        'clan': clan,
        'chief': chief,
        'person': person,
        'predecessor': line[i - 1] if i > 0 else None,
        'successor': line[i + 1] if i + 1 < len(line) else None,
        'line': line,
        'evidence': chief.attachments.public(),
    })
