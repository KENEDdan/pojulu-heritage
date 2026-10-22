from django.urls import path
from . import views

app_name = 'wills'

urlpatterns = [
    path('login/',            views.family_login,          name='login'),
    path('logout/',           views.family_logout,         name='logout'),
    path('change-password/',  views.family_change_password, name='change_password'),
    path('',                  views.family_dashboard,       name='dashboard'),
    path('my-will/',          views.family_will_write,      name='will_write'),
    path('my-will/read/',     views.family_will_read,       name='will_read'),
    path('will/<int:pk>/',    views.family_will_view,       name='will_view'),
]
