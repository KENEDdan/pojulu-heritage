from django.core.cache import cache
from django.shortcuts import render
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit
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
from apps.core.utils import MAX_QUERY_LENGTH, MIN_QUERY_LENGTH, search_term

IP_KEY = 'apps.core.net.ratelimit_ip_key'


HOME_CACHE_SECONDS = 60


def _home_news():
    featured = NewsPost.objects.public().filter(is_featured=True).first()
    return {
        'featured_post': featured,
        'side_posts': list(NewsPost.objects.public().exclude(pk=featured.pk if featured else 0)
                           .order_by('-published_at')[:2]),
        'news_posts': list(NewsPost.objects.public().order_by('-published_at')[:6]),
        'events': list(NewsPost.objects.public().filter(post_type='event').order_by('event_date')[:3]),
    }


def _home_stats():
    stats, _ = SiteStats.objects.get_or_create(pk=1)
    return {
        'clans':      Clan.objects.public().count() or stats.clans_count,
        'families':   Family.objects.public().count() or stats.families_count,
        'persons':    Person.objects.public().count() or stats.persons_count,
        'memorial':   MemorialRecord.objects.public().count() or stats.memorial_count,
        'interviews': ElderInterview.objects.public().count() or stats.interviews_count,
    }


@method_decorator(ratelimit(key=IP_KEY, rate='120/m', method='GET', block=True), name='get')
class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Archive highlights
        ctx['featured_clans']        = Clan.objects.public().with_counts().prefetch_related('bomas').filter(is_featured=True).order_by('name')[:6]
        ctx['recent_persons']        = Person.objects.public().select_related('clan').order_by('-created_at')[:5]
        ctx['recent_memorials']      = MemorialRecord.objects.public().select_related('person', 'person__clan').order_by('-created_at')[:3]
        ctx['featured_achievements'] = Achievement.objects.public().select_related('clan').filter(is_featured=True).order_by('-year')[:3]
        ctx['recent_interviews']     = ElderInterview.objects.public().select_related('clan').order_by('-interview_date')[:3]
        ctx['announcements']         = Announcement.objects.filter(is_active=True)[:2]

        ctx.update(cache.get_or_set('home:news', _home_news, HOME_CACHE_SECONDS))
        ctx['stats'] = cache.get_or_set('home:stats', _home_stats, HOME_CACHE_SECONDS)
        return ctx


class AboutView(TemplateView):
    template_name = 'core/about.html'


@method_decorator(ratelimit(key=IP_KEY, rate='30/m', method='GET', block=True), name='get')
class SearchView(TemplateView):
    template_name = 'core/search_results.html'

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        q    = search_term(self.request)
        kind = self.request.GET.get('kind', 'all')
        ctx['query'] = q
        ctx['kind']  = kind
        ctx['max_query_length'] = MAX_QUERY_LENGTH
        if not q: return ctx
        if len(q) < MIN_QUERY_LENGTH:
            ctx.update(query_too_short=True, results={}, total_results=0)
            return ctx
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


@ratelimit(key=IP_KEY, rate='120/m', block=True)
def private_media(request, name):
    """Authenticated gate for every file in private storage."""
    from apps.core.private_media import serve
    return serve(request, name)


@require_GET
def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /dashboard/',
        'Disallow: /admin/',
        'Disallow: /family/',
        'Disallow: /private-media/',
        'Disallow: /healthz',
        'Disallow: /search/',
        '',
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')


def ratelimited(request, exception=None):
    """RATELIMIT_VIEW: rendered when a client exceeds a rate limit."""
    return render(request, '429.html', status=429)
