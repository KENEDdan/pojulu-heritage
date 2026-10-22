from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Marriage

class MarriageListView(ListView):
    model = Marriage
    template_name = 'marriages/list.html'
    context_object_name = 'marriages'
    paginate_by = 20

    def get_queryset(self):
        qs = Marriage.objects.public().select_related('husband_clan','wife_clan','husband','wife','husband__clan','wife__clan')
        q = self.request.GET.get('q','')
        clan = self.request.GET.get('clan','')
        if q:
            qs = qs.filter(Q(husband_name__icontains=q)|Q(wife_name__icontains=q)|Q(husband__first_name__icontains=q)|Q(wife__first_name__icontains=q))
        if clan:
            qs = qs.filter(Q(husband_clan__slug=clan)|Q(wife_clan__slug=clan))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q','')
        ctx['selected_clan'] = self.request.GET.get('clan','')
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.public().values('name','slug')
        return ctx

class MarriageDetailView(DetailView):
    model = Marriage
    template_name = 'marriages/detail.html'
    context_object_name = 'marriage'
    queryset = Marriage.objects.public().select_related('husband', 'wife', 'husband_clan', 'wife_clan',
                                                        'husband__clan', 'wife__clan')
