from django.conf import settings
from apps.core.utils import search_term
from django.views.generic import ListView, DetailView
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from .models import Family, Person
from .relatives import family_generations, relatives_of, relatives_summary, walk_ancestors, walk_descendants


class FamilyListView(ListView):
    model = Family
    template_name = 'genealogy/list.html'
    context_object_name = 'families'
    paginate_by = settings.RECORDS_PER_PAGE

    def get_queryset(self):
        qs = Family.objects.public().with_counts().select_related('clan').order_by('name')
        q = search_term(self.request)
        clan = self.request.GET.get('clan', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if clan:
            qs = qs.filter(clan__slug=clan)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['query'] = search_term(self.request)
        ctx['selected_clan'] = self.request.GET.get('clan', '')
        from apps.clans.models import Clan
        ctx['clans'] = Clan.objects.public().values('name', 'slug')
        return ctx


class FamilyDetailView(DetailView):
    model = Family
    template_name = 'genealogy/family_detail.html'
    context_object_name = 'family'
    queryset = Family.objects.public()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        family = self.object
        ctx['members'] = family.person_set.public().order_by('birth_year', 'last_name')
        ctx['roots'] = family.person_set.public().filter(father__isnull=True)
        ctx['chapters'] = family.chapters.all()
        ctx['generations'] = family_generations(family)
        ctx['evidence'] = family.attachments.public()
        return ctx


class PersonDetailView(DetailView):
    model = Person
    template_name = 'genealogy/person_detail.html'
    context_object_name = 'person'
    queryset = Person.objects.public().select_related('clan', 'family')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['relatives'] = self.object.public_relatives()
        sections = relatives_of(self.object)
        ctx['relative_sections'] = sections
        ctx['relatives_summary'] = relatives_summary(self.object, sections)
        ctx['relatives_total'] = sum(s['count'] for s in sections)
        ctx['chief_roles'] = self.object.chief_roles.filter(clan__is_verified=True, clan__is_deleted=False)             .select_related('clan')
        return ctx


DEFAULT_TREE_GENERATIONS = 4
MAX_TREE_GENERATIONS = 10


def _ancestor_relation_label(gender, generation):
    if generation == 1:
        return {'M': 'Father', 'F': 'Mother'}.get(gender, 'Parent')
    label = ('Great-' * (generation - 2)) + {'M': 'grandfather', 'F': 'grandmother'}.get(gender, 'grandparent')
    return label[0].upper() + label[1:]


def _descendant_relation_label(gender, generation):
    if generation == 1:
        return {'M': 'Son', 'F': 'Daughter'}.get(gender, 'Child')
    label = ('Great-' * (generation - 2)) + {'M': 'grandson', 'F': 'granddaughter'}.get(gender, 'grandchild')
    return label[0].upper() + label[1:]


def _generation_row_title(generation, direction):
    noun = 'Grandparents' if direction == 'up' else 'Grandchildren'
    base = 'Parents' if (direction == 'up' and generation == 1) else \
           'Children' if (direction == 'down' and generation == 1) else None
    if base:
        return base
    return ('Great-' * (generation - 2)) + noun


@ratelimit(key='apps.core.net.ratelimit_ip_key', rate='30/m', method='GET', block=True)
def family_tree(request, slug):
    person = get_object_or_404(Person.objects.public(), slug=slug)

    try:
        requested_generations = int(request.GET.get('gens', DEFAULT_TREE_GENERATIONS))
    except (TypeError, ValueError):
        requested_generations = DEFAULT_TREE_GENERATIONS
    generations = max(1, min(requested_generations, MAX_TREE_GENERATIONS))

    ancestor_data, ancestors_truncated = walk_ancestors(person, generations)
    descendant_data, descendants_truncated = walk_descendants(person, generations)

    ancestor_rows = [{
        'generation': i,
        'title': _generation_row_title(i, 'up'),
        'members': [{
            'person': p,
            'relation': _ancestor_relation_label(p.gender, i),
            'path': ' → '.join(path),
        } for p, path in gen_people],
    } for i, gen_people in enumerate(ancestor_data, start=1)]
    ancestor_rows.reverse()  # farthest ancestors render first (top of chart)

    descendant_rows = [{
        'generation': i,
        'title': _generation_row_title(i, 'down'),
        'members': [{
            'person': p,
            'relation': _descendant_relation_label(p.gender, i),
        } for p in gen_people],
    } for i, gen_people in enumerate(descendant_data, start=1)]

    # ── Immediate collaterals: siblings, aunts/uncles, cousins, nieces/nephews.
    # Kept at one level regardless of the N-generation depth control above —
    # a full N-generation collateral expansion (great-aunts, their
    # descendants, ...) grows combinatorially and isn't shown here.
    # One query per relationship tier (not per relative), and every tier
    # excludes people already shown, so even corrupt data that loops back on
    # itself can't repeat or recurse.
    relatives = person.public_relatives()
    public = Person.objects.public()
    parents = [p for p in [relatives['father'], relatives['mother']] if p]
    parent_ids = {p.pk for p in parents}
    grandparent_ids = {x for p in parents for x in (p.father_id, p.mother_id) if x}

    def children_of(ids, exclude):
        if not ids:
            return []
        return list(public.filter(Q(father_id__in=ids) | Q(mother_id__in=ids))
                    .exclude(pk__in=exclude).distinct())

    shown = {person.pk} | parent_ids
    aunts_uncles = children_of(grandparent_ids, shown)
    siblings = relatives['siblings']
    shown |= {p.pk for p in aunts_uncles} | {p.pk for p in siblings}
    cousins = children_of({a.pk for a in aunts_uncles}, shown)
    shown |= {c.pk for c in cousins}
    nieces_nephews = children_of({s.pk for s in siblings}, shown)

    return render(request, 'genealogy/tree.html', {
        'person': person,
        'ancestor_rows': ancestor_rows,
        'descendant_rows': descendant_rows,
        'ancestors_truncated': ancestors_truncated,
        'descendants_truncated': descendants_truncated,
        'aunts_uncles': aunts_uncles,
        'siblings': siblings,
        'cousins': cousins,
        'nieces_nephews': nieces_nephews,
        'spouses': relatives['spouses'],
        'generations': generations,
        'default_generations': DEFAULT_TREE_GENERATIONS,
        'max_generations': MAX_TREE_GENERATIONS,
    })