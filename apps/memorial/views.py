from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import MemorialRecord

class MemorialListView(ListView):
    model = MemorialRecord
    template_name = 'memorial/list.html'
    context_object_name = 'memorials'
    paginate_by = 12

    def get_queryset(self):
        qs = MemorialRecord.objects.select_related('person','person__clan').order_by('-person__death_year','-created_at')
        q = self.request.GET.get('q','')
        clan = self.request.GET.get('clan','')
        if q:
            qs = qs.filter(Q(person__first_name__icontains=q)|Q(person__last_name__icontains=q)|Q(tribute__icontains=q))
        if clan:
            qs = qs.filter(person__clan__slug=clan)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q','')
        ctx['selected_clan'] = self.request.GET.get('clan','')
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.filter(is_verified=True).values('name','slug')
        return ctx

class MemorialDetailView(DetailView):
    model = MemorialRecord
    template_name = 'memorial/detail.html'
    context_object_name = 'memorial'
