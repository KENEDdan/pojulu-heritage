from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title  = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE

urlpatterns = [
    path('admin/',        admin.site.urls),
    path('',              include('apps.core.urls',         namespace='core')),
    path('clans/',        include('apps.clans.urls',        namespace='clans')),
    path('families/',     include('apps.genealogy.urls',    namespace='genealogy')),
    path('memorial/',     include('apps.memorial.urls',     namespace='memorial')),
    path('achievements/', include('apps.achievements.urls', namespace='achievements')),
    path('marriages/',    include('apps.marriages.urls',    namespace='marriages')),
    path('culture/',      include('apps.cultural.urls',     namespace='cultural')),
    path('elders/',       include('apps.elders.urls',       namespace='elders')),
    path('submit/',       include('apps.submissions.urls',  namespace='submissions')),
    path('dashboard/',    include('apps.dashboard.urls',    namespace='dashboard')),
    path('news/',         include('apps.news.urls',         namespace='news')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,  document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,   document_root=settings.MEDIA_ROOT)