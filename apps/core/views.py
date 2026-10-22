from django.shortcuts import render
from django.views.generic import TemplateView
from django.db.models import Q
from apps.clans.models import Clan
from apps.genealogy.models import Person, Family
from apps.memorial.models import MemorialRecord
from apps.achievements.models import Achievement
from apps.marriages.models import Marriage
from apps.cultural.models import CulturalRecord
from apps.elders.models import ElderInterview
from apps.core.models import SiteStats, Announcement
from apps.news.models import NewsPost


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Archive highlights
        ctx['featured_clans']        = Clan.objects.public().filter(is_featured=True)[:6]
        ctx['recent_persons']        = Person.objects.public().order_by('-created_at')[:5]
        ctx['recent_memorials']      = MemorialRecord.objects.public().select_related('person', 'person__clan').order_by('-created_at')[:3]
        ctx['featured_achievements'] = Achievement.objects.public().filter(is_featured=True).order_by('-year')[:3]
        ctx['recent_interviews']     = ElderInterview.objects.public().order_by('-interview_date')[:3]
        ctx['announcements']         = Announcement.objects.filter(is_active=True)[:2]

        # News feed
        ctx['featured_post'] = NewsPost.objects.public().filter(is_featured=True).first()
        ctx['side_posts']    = NewsPost.objects.public().exclude(
            pk=ctx['featured_post'].pk if ctx['featured_post'] else 0
        ).order_by('-published_at')[:2]
        ctx['news_posts']    = NewsPost.objects.public().order_by('-published_at')[:6]
        ctx['events']        = NewsPost.objects.public().filter(post_type='event').order_by('event_date')[:3]

        # Stats
        stats, _ = SiteStats.objects.get_or_create(pk=1)
        ctx['stats'] = {
            'clans':      Clan.objects.public().count() or stats.clans_count,
            'families':   Family.objects.public().count() or stats.families_count,
            'persons':    Person.objects.public().count() or stats.persons_count,
            'memorial':   MemorialRecord.objects.public().count() or stats.memorial_count,
            'interviews': ElderInterview.objects.public().count() or stats.interviews_count,
        }
        return ctx


class AboutView(TemplateView):
    template_name = 'core/about.html'


class SearchView(TemplateView):
    template_name = 'core/search_results.html'

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        q    = self.request.GET.get('q', '').strip()
        kind = self.request.GET.get('kind', 'all')
        ctx['query'] = q
        ctx['kind']  = kind
        if not q: return ctx
        results = {}
        if kind in ('all', 'clans'):
            results['clans'] = Clan.objects.public().filter(
                Q(name__icontains=q) | Q(description__icontains=q))[:10]
        if kind in ('all', 'persons'):
            results['persons'] = Person.objects.public().filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(biography__icontains=q)
            ).select_related('clan')[:15]
        if kind in ('all', 'families'):
            results['families'] = Family.objects.public().filter(
                Q(name__icontains=q) | Q(description__icontains=q)).select_related('clan')[:10]
        if kind in ('all', 'memorial'):
            results['memorial'] = MemorialRecord.objects.public().filter(
                Q(person__first_name__icontains=q) | Q(person__last_name__icontains=q)).select_related('person', 'person__clan')[:10]
        if kind in ('all', 'achievements'):
            results['achievements'] = Achievement.objects.public().filter(
                Q(person_name__icontains=q) | Q(title__icontains=q))[:8]
        if kind in ('all', 'news'):
            results['news'] = NewsPost.objects.public().filter(
                Q(title__icontains=q) | Q(excerpt__icontains=q))[:6]
        ctx['results']       = results
        ctx['total_results'] = sum(len(v) for v in results.values())
        return ctx

def healthz(request):
    """Liveness/readiness probe for Railway. Reports only up/down — never
    versions, hostnames, or error details."""
    from django.db import connection
    from django.http import JsonResponse
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'error', 'database': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'ok'})


def private_media(request, name):
    """Authenticated gate for every file in private storage."""
    from apps.core.private_media import serve
    return serve(request, name)
