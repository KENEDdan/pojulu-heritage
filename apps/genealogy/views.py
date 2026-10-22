from apps.core.utils import search_term
from django.views.generic import ListView, DetailView
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from .models import Family, Person


class FamilyListView(ListView):
    model = Family
    template_name = 'genealogy/list.html'
    context_object_name = 'families'
    paginate_by = 12

    def get_queryset(self):
        qs = Family.objects.public().select_related('clan')
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
        ctx['members'] = self.object.person_set.public().order_by('birth_year', 'last_name')
        ctx['roots'] = self.object.person_set.public().filter(father__isnull=True)
        return ctx


class PersonDetailView(DetailView):
    model = Person
    template_name = 'genealogy/person_detail.html'
    context_object_name = 'person'
    queryset = Person.objects.public().select_related('clan', 'family')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['relatives'] = self.object.public_relatives()
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


def _walk_ancestors(person, max_generations):
    """BFS upward from `person`. Returns (generations, truncated) where
    generations is a list (index 0 = parents) of lists of (Person, path)
    tuples; path is the chain of 'Father'/'Mother' steps taken to reach
    them, used to disambiguate e.g. paternal vs maternal great-grandparents.
    Stops at unverified records (same visibility rule as the rest of the
    site) and de-duplicates by pk, so a lineage that loops back on itself
    (e.g. clan-endogamous marriages producing a shared ancestor) is shown
    once, at the generation it was first reached.
    """
    generations = []
    visited = {person.pk}
    frontier = [(person, [])]
    truncated = False
    for gen in range(1, max_generations + 1):
        parent_ids = set()
        for p, _ in frontier:
            if p.father_id:
                parent_ids.add(p.father_id)
            if p.mother_id:
                parent_ids.add(p.mother_id)
        parent_ids -= visited
        if not parent_ids:
            break
        people_map = {pp.pk: pp for pp in Person.objects.public().filter(pk__in=parent_ids)}
        next_frontier = []
        seen_this_gen = set()
        for p, path in frontier:
            for parent_id, rel in ((p.father_id, 'Father'), (p.mother_id, 'Mother')):
                if parent_id and parent_id in people_map and parent_id not in seen_this_gen:
                    seen_this_gen.add(parent_id)
                    next_frontier.append((people_map[parent_id], path + [rel]))
        if not next_frontier:
            break
        visited.update(seen_this_gen)
        generations.append(next_frontier)
        frontier = next_frontier
        if gen == max_generations:
            more_ids = set()
            for p, _ in frontier:
                if p.father_id and p.father_id not in visited:
                    more_ids.add(p.father_id)
                if p.mother_id and p.mother_id not in visited:
                    more_ids.add(p.mother_id)
            truncated = bool(more_ids)
    return generations, truncated


def _walk_descendants(person, max_generations):
    """BFS downward from `person`. Returns (generations, truncated) where
    generations is a list (index 0 = children) of lists of Person.
    """
    generations = []
    visited = {person.pk}
    frontier_ids = [person.pk]
    truncated = False
    for gen in range(1, max_generations + 1):
        children = list(Person.objects.public().filter(
            Q(father_id__in=frontier_ids) | Q(mother_id__in=frontier_ids)
        ).exclude(pk__in=visited).distinct())
        if not children:
            break
        visited.update(c.pk for c in children)
        generations.append(children)
        frontier_ids = [c.pk for c in children]
        if gen == max_generations:
            truncated = Person.objects.public().filter(
                Q(father_id__in=frontier_ids) | Q(mother_id__in=frontier_ids)
            ).exclude(pk__in=visited).exists()
    return generations, truncated


@ratelimit(key='apps.core.net.ratelimit_ip_key', rate='30/m', method='GET', block=True)
def family_tree(request, slug):
    person = get_object_or_404(Person.objects.public(), slug=slug)

    try:
        requested_generations = int(request.GET.get('gens', DEFAULT_TREE_GENERATIONS))
    except (TypeError, ValueError):
        requested_generations = DEFAULT_TREE_GENERATIONS
    generations = max(1, min(requested_generations, MAX_TREE_GENERATIONS))

    ancestor_data, ancestors_truncated = _walk_ancestors(person, generations)
    descendant_data, descendants_truncated = _walk_descendants(person, generations)

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