from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap

from apps.core.sitemaps import SITEMAPS
from apps.core.views import robots_txt

urlpatterns = [
    path('robots.txt',    robots_txt, name='robots_txt'),
    path('sitemap.xml',   sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('',              include('apps.core.urls',         namespace='core')),
    path('clans/',        include('apps.clans.urls',        namespace='clans')),
    path('families/',     include('apps.genealogy.urls',    namespace='genealogy')),
    path('memorial/',     include('apps.memorial.urls',     namespace='memorial')),
    path('achievements/', include('apps.achievements.urls', namespace='achievements')),
    path('marriages/',    include('apps.marriages.urls',    namespace='marriages')),
    path('culture/',      include('apps.cultural.urls',     namespace='cultural')),
    path('elders/',       include('apps.elders.urls',       namespace='elders')),
    path('dashboard/',    include('apps.dashboard.urls',    namespace='dashboard')),
    path('news/',         include('apps.news.urls',         namespace='news')),
    path('family/',       include('apps.wills.urls',        namespace='wills')),
]

# The Django admin is off unless ENABLE_DJANGO_ADMIN=True, and is never linked
# from the site. Role-scoped admins (clan_admin, ...) hold raw model
# permissions for the /dashboard/ views; those must not let them into the
# un-gated admin, so it is restricted to superusers.
if settings.ENABLE_DJANGO_ADMIN:
    admin.site.site_header = settings.ADMIN_SITE_HEADER
    admin.site.site_title  = settings.ADMIN_SITE_TITLE
    admin.site.index_title = settings.ADMIN_INDEX_TITLE
    from apps.dashboard.twofactor import superadmin_2fa_ok
    admin.site.has_permission = lambda request: (request.user.is_active and request.user.is_superuser
                                                 and superadmin_2fa_ok(request.user))
    urlpatterns.insert(0, path(settings.ADMIN_URL_PREFIX, admin.site.urls))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
