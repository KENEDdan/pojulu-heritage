from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import ElderInterview

class ElderListView(ListView):
    model = ElderInterview
    template_name = 'elders/list.html'
    context_object_name = 'interviews'
    paginate_by = 12

    def get_queryset(self):
        qs = ElderInterview.objects.filter(is_published=True).select_related('clan')
        q = self.request.GET.get('q','')
        clan = self.request.GET.get('clan','')
        if q:
            qs = qs.filter(Q(elder_name__icontains=q)|Q(summary__icontains=q)|Q(topics_covered__icontains=q))
        if clan:
            qs = qs.filter(clan__slug=clan)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q','')
        ctx['selected_clan'] = self.request.GET.get('clan','')
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.filter(is_verified=True).values('name','slug')
        return ctx

class ElderDetailView(DetailView):
    model = ElderInterview
    template_name = 'elders/detail.html'
    context_object_name = 'interview'
    queryset = ElderInterview.objects.filter(is_published=True)
