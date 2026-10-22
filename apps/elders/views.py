from django.conf import settings
from apps.core.utils import search_term
from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import ElderInterview

class ElderListView(ListView):
    model = ElderInterview
    template_name = 'elders/list.html'
    context_object_name = 'interviews'
    paginate_by = settings.RECORDS_PER_PAGE

    def get_queryset(self):
        qs = ElderInterview.objects.public().select_related('clan')
        q = search_term(self.request)
        clan = self.request.GET.get('clan','')
        if q:
            qs = qs.filter(Q(elder_name__icontains=q)|Q(summary__icontains=q)|Q(topics_covered__icontains=q))
        if clan:
            qs = qs.filter(clan__slug=clan)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = search_term(self.request)
        ctx['selected_clan'] = self.request.GET.get('clan','')
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.public().values('name','slug')
        return ctx

class ElderDetailView(DetailView):
    model = ElderInterview
    template_name = 'elders/detail.html'
    context_object_name = 'interview'
    queryset = ElderInterview.objects.public().select_related('clan')
