from django.urls import path
from . import views
app_name = 'elders'
urlpatterns = [
    path('',          views.ElderListView.as_view(),   name='list'),
    path('<int:pk>/', views.ElderDetailView.as_view(), name='detail'),
]
