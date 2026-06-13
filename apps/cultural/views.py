from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import CulturalRecord, RECORD_TYPE_CHOICES

class CulturalListView(ListView):
    model = CulturalRecord
    template_name = 'cultural/list.html'
    context_object_name = 'records'
    paginate_by = 16

    def get_queryset(self):
        qs = CulturalRecord.objects.filter(is_verified=True).select_related('clan')
        q = self.request.GET.get('q','')
        rtype = self.request.GET.get('type','')
        if q:
            qs = qs.filter(Q(title__icontains=q)|Q(content__icontains=q))
        if rtype:
            qs = qs.filter(record_type=rtype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q','')
        ctx['selected_type'] = self.request.GET.get('type','')
        ctx['type_choices'] = RECORD_TYPE_CHOICES
        return ctx

class CulturalDetailView(DetailView):
    model = CulturalRecord
    template_name = 'cultural/detail.html'
    context_object_name = 'record'
    queryset = CulturalRecord.objects.filter(is_verified=True)
