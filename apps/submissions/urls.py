from django.urls import path
from django.views.generic import RedirectView

app_name = 'submissions'

urlpatterns = [
    # Public submissions removed — records are managed through the admin panel only.
    # Any old links redirect to the about page.
    path('', RedirectView.as_view(pattern_name='core:about', permanent=False), name='form'),
    path('success/', RedirectView.as_view(pattern_name='core:about', permanent=False), name='success'),
]