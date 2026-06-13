from django.urls import path
from . import views
app_name = 'marriages'
urlpatterns = [
    path('',          views.MarriageListView.as_view(),   name='list'),
    path('<int:pk>/', views.MarriageDetailView.as_view(), name='detail'),
]
