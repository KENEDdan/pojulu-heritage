from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Q, F
from .models import NewsPost


class NewsListView(ListView):
    model               = NewsPost
    template_name       = 'news/list.html'
    context_object_name = 'posts'
    paginate_by         = 12

    def get_queryset(self):
        qs       = NewsPost.objects.filter(is_published=True)
        q        = self.request.GET.get('q', '')
        pt       = self.request.GET.get('type', '')
        if q:  qs = qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q))
        if pt: qs = qs.filter(post_type=pt)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query']        = self.request.GET.get('q', '')
        ctx['selected_type'] = self.request.GET.get('type', '')
        ctx['type_choices'] = [('news','News'),('event','Event'),('announcement','Announcement'),('story','Story'),('update','Update')]
        return ctx


class NewsDetailView(DetailView):
    model               = NewsPost
    template_name       = 'news/detail.html'
    context_object_name = 'post'
    queryset            = NewsPost.objects.filter(is_published=True)

    def get_object(self):
        obj = super().get_object()
        NewsPost.objects.filter(pk=obj.pk).update(views=F('views') + 1)
        return obj

    def get_context_data(self, **kwargs):
        ctx          = super().get_context_data(**kwargs)
        ctx['media'] = self.object.media.all()
        ctx['related'] = NewsPost.objects.filter(
            is_published=True, post_type=self.object.post_type
        ).exclude(pk=self.object.pk)[:3]
        return ctx