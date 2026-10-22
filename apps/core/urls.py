from django.urls import path
from . import views
app_name = 'core'
urlpatterns = [
    path('',        views.HomeView.as_view(),   name='home'),
    path('about/',  views.AboutView.as_view(),  name='about'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('healthz', views.healthz, name='healthz'),
    path('healthz/', views.healthz),
    path('private-media/<path:name>', views.private_media, name='private_media'),
]
