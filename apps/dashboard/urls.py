from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Auth
    path('login/',   views.dashboard_login,  name='login'),
    path('logout/',  views.dashboard_logout, name='logout'),

    # Superadmin home
    path('', views.home, name='home'),

    # Role dashboards
    path('clans/',        views.clan_dashboard,        name='clan_dashboard'),
    path('genealogy/',    views.genealogy_dashboard,    name='genealogy_dashboard'),
    path('memorial/',     views.memorial_dashboard,     name='memorial_dashboard'),
    path('cultural/',     views.cultural_dashboard,     name='cultural_dashboard'),
    path('elders/',       views.elder_dashboard,        name='elder_dashboard'),
    path('achievements/', views.achievement_dashboard,  name='achievement_dashboard'),
    path('content/',      views.content_dashboard,      name='content_dashboard'),

    # Clan CRUD
    path('clans/add/',               views.clan_add,     name='clan_add'),
    path('clans/<int:pk>/edit/',     views.clan_edit,    name='clan_edit'),
    path('clans/<int:pk>/delete/',   views.clan_delete,  name='clan_delete'),
    path('chiefs/add/',              views.chief_add,    name='chief_add'),
    path('chiefs/<int:pk>/edit/',    views.chief_edit,   name='chief_edit'),
    path('chiefs/<int:pk>/delete/',  views.chief_delete, name='chief_delete'),
    path('events/add/',              views.event_add,    name='event_add'),
    path('events/<int:pk>/edit/',    views.event_edit,   name='event_edit'),
    path('events/<int:pk>/delete/',  views.event_delete, name='event_delete'),

    # Person & Family CRUD
    path('persons/add/',              views.person_add,    name='person_add'),
    path('persons/<int:pk>/edit/',    views.person_edit,   name='person_edit'),
    path('persons/<int:pk>/delete/',  views.person_delete, name='person_delete'),
    path('families/add/',             views.family_add,    name='family_add'),
    path('families/<int:pk>/edit/',   views.family_edit,   name='family_edit'),
    path('families/<int:pk>/delete/', views.family_delete, name='family_delete'),

    # Marriage CRUD
    path('marriages/add/',             views.marriage_add,    name='marriage_add'),
    path('marriages/<int:pk>/edit/',   views.marriage_edit,   name='marriage_edit'),
    path('marriages/<int:pk>/delete/', views.marriage_delete, name='marriage_delete'),

    # Memorial CRUD
    path('memorial/add/',             views.memorial_add,    name='memorial_add'),
    path('memorial/<int:pk>/edit/',   views.memorial_edit,   name='memorial_edit'),
    path('memorial/<int:pk>/delete/', views.memorial_delete, name='memorial_delete'),

    # Achievement CRUD
    path('achievements/add/',             views.achievement_add,    name='achievement_add'),
    path('achievements/<int:pk>/edit/',   views.achievement_edit,   name='achievement_edit'),
    path('achievements/<int:pk>/delete/', views.achievement_delete, name='achievement_delete'),

    # Cultural CRUD
    path('cultural/add/',             views.cultural_add,    name='cultural_add'),
    path('cultural/<int:pk>/edit/',   views.cultural_edit,   name='cultural_edit'),
    path('cultural/<int:pk>/delete/', views.cultural_delete, name='cultural_delete'),

    # Elder Interview CRUD
    path('elder-interviews/add/',             views.elder_add,    name='elder_add'),
    path('elder-interviews/<int:pk>/edit/',   views.elder_edit,   name='elder_edit'),
    path('elder-interviews/<int:pk>/delete/', views.elder_delete, name='elder_delete'),

    # Submission Review
    path('submissions/',                  views.submission_list,   name='submission_list'),
    path('submissions/<int:pk>/review/',  views.submission_review, name='submission_review'),

    # Account management
    path('accounts/',                        views.manage_accounts,   name='accounts'),
    path('accounts/create/',                 views.create_account,    name='create_account'),
    path('accounts/<int:pk>/edit/',          views.edit_account,      name='edit_account'),
    path('accounts/<int:pk>/deactivate/',    views.deactivate_account, name='deactivate_account'),
    path('accounts/<int:pk>/reactivate/',    views.reactivate_account, name='reactivate_account'),
]