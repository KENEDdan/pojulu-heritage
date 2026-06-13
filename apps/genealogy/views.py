from django.views.generic import ListView, DetailView
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Family, Person


class FamilyListView(ListView):
    model = Family
    template_name = 'genealogy/list.html'
    context_object_name = 'families'
    paginate_by = 12

    def get_queryset(self):
        qs = Family.objects.filter(is_verified=True).select_related('clan')
        q = self.request.GET.get('q', '')
        clan = self.request.GET.get('clan', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if clan:
            qs = qs.filter(clan__slug=clan)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = self.request.GET.get('q', '')
        ctx['selected_clan'] = self.request.GET.get('clan', '')
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.filter(is_verified=True).values('name', 'slug')
        return ctx


class FamilyDetailView(DetailView):
    model = Family
    template_name = 'genealogy/family_detail.html'
    context_object_name = 'family'
    queryset = Family.objects.filter(is_verified=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['members'] = self.object.person_set.filter(is_verified=True).order_by('birth_year', 'last_name')
        ctx['roots'] = self.object.person_set.filter(is_verified=True, father__isnull=True)
        return ctx


class PersonDetailView(DetailView):
    model = Person
    template_name = 'genealogy/person_detail.html'
    context_object_name = 'person'
    queryset = Person.objects.filter(is_verified=True)


def family_tree(request, slug):
    person = get_object_or_404(Person, slug=slug, is_verified=True)

    # ── Generation -2: Grandparents ──
    grandparents = []
    for parent in [person.father, person.mother]:
        if parent:
            if parent.father:
                grandparents.append(parent.father)
            if parent.mother:
                grandparents.append(parent.mother)

    # ── Generation -1: Parents + their siblings (uncles/aunts) ──
    parents = [p for p in [person.father, person.mother] if p]
    aunts_uncles = []
    for parent in parents:
        for sib in parent.siblings.filter(is_verified=True):
            aunts_uncles.append(sib)

    # ── Generation 0: Person + siblings ──
    siblings = list(person.siblings.filter(is_verified=True))

    # ── Cousins (children of aunts/uncles) ──
    cousins = []
    for au in aunts_uncles:
        for child in au.children.filter(is_verified=True):
            cousins.append(child)

    # ── Generation +1: Children + nieces/nephews ──
    children = list(person.children.filter(is_verified=True))
    nieces_nephews = []
    for sib in siblings:
        for child in sib.children.filter(is_verified=True):
            nieces_nephews.append(child)

    return render(request, 'genealogy/tree.html', {
        'person': person,
        'grandparents': grandparents,
        'parents': parents,
        'aunts_uncles': aunts_uncles,
        'siblings': siblings,
        'cousins': cousins,
        'children': children,
        'nieces_nephews': nieces_nephews,
        'spouses': person.spouses,
    })