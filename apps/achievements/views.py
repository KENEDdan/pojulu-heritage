from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Achievement, CATEGORY_CHOICES

class AchievementListView(ListView):
    model = Achievement
    template_name = 'achievements/list.html'
    context_object_name = 'achievements'
    paginate_by = 15

    def get_queryset(self):
        qs = Achievement.objects.filter(is_verified=True).select_related('clan')
        q = self.request.GET.get('q','')
        cat = self.request.GET.get('category','')
        if q:
            qs = qs.filter(Q(person_name__icontains=q)|Q(title__icontains=q)|Q(description__icontains=q))
        if cat:
            qs = qs.filter(category=cat)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q','')
        ctx['selected_category'] = self.request.GET.get('category','')
        ctx['category_choices'] = CATEGORY_CHOICES
        return ctx

class AchievementDetailView(DetailView):
    model = Achievement
    template_name = 'achievements/detail.html'
    context_object_name = 'achievement'
