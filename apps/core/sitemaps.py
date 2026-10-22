from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.clans.models import Clan
from apps.elders.models import ElderInterview
from apps.genealogy.models import Family, Person
from apps.news.models import NewsPost


class StaticSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return ['core:home', 'core:about', 'clans:list', 'genealogy:list', 'memorial:list',
                'achievements:list', 'marriages:list', 'cultural:list', 'elders:list', 'news:list']

    def location(self, item):
        return reverse(item)


class ClanSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        return Clan.objects.public().order_by('pk')

    def lastmod(self, obj):
        return obj.updated_at


class FamilySitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Family.objects.public().order_by('pk')

    def lastmod(self, obj):
        return obj.updated_at


class PersonSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5
    limit = 5000

    def items(self):
        # .public() already excludes private living people.
        return Person.objects.public().order_by('pk')

    def lastmod(self, obj):
        return obj.updated_at


class NewsSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return NewsPost.objects.public().order_by('-published_at')

    def lastmod(self, obj):
        return obj.updated_at


class InterviewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return ElderInterview.objects.public().order_by('pk')

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    'static': StaticSitemap,
    'clans': ClanSitemap,
    'families': FamilySitemap,
    'people': PersonSitemap,
    'news': NewsSitemap,
    'interviews': InterviewSitemap,
}
