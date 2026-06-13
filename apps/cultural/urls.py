from django.urls import path
from . import views
app_name = 'cultural'
urlpatterns = [
    path('',              views.CulturalListView.as_view(),   name='list'),
    path('<slug:slug>/',  views.CulturalDetailView.as_view(), name='detail'),
]
