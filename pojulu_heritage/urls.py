from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title  = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE

# Role-scoped admins (clan_admin, genealogy_admin, ...) are granted raw Django
# model permissions (including delete) in AdminProfile.assign_permissions() so
# they can use the role-gated /dashboard/ views. Those same permissions would
# otherwise let them reach the un-gated Django admin at /admin/ and bypass
# dashboard-only restrictions (e.g. delete is superadmin-only in the
# dashboard). /admin/ is reserved for superusers; scoped admins use /dashboard/.
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser

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
    path('family/',       include('apps.wills.urls',        namespace='wills')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,  document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,   document_root=settings.MEDIA_ROOT)