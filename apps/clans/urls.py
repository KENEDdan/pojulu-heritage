from django.urls import path
from . import views
app_name = 'clans'
urlpatterns = [
    path('',          views.ClanListView.as_view(),   name='list'),
    path('<slug:slug>/', views.ClanDetailView.as_view(), name='detail'),
    path('<slug:slug>/chiefs/<int:pk>/', views.chief_detail, name='chief_detail'),
]
