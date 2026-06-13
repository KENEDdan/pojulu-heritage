from django.urls import path
from . import views
app_name = 'memorial'
urlpatterns = [
    path('',         views.MemorialListView.as_view(),   name='list'),
    path('<int:pk>/', views.MemorialDetailView.as_view(), name='detail'),
]
