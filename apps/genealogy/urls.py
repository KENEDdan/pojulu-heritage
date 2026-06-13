from django.urls import path
from . import views

app_name = 'genealogy'

urlpatterns = [
    path('',                              views.FamilyListView.as_view(),   name='list'),
    path('family/<slug:slug>/',           views.FamilyDetailView.as_view(), name='family_detail'),
    path('person/<slug:slug>/',           views.PersonDetailView.as_view(), name='person_detail'),
    path('person/<slug:slug>/tree/',      views.family_tree,                name='person_tree'),  # ← was wrongly using .as_view()
    path('<slug:slug>/tree/',             views.family_tree,                name='tree'),
]