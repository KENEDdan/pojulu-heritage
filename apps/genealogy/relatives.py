"""Written genealogy: every relative of a person, and a family told
generation by generation.

A tree can't show four grandparents, eight great-grandparents, dozens of
siblings and all the cousins at once, so these helpers produce complete,
labelled lists for the person and family pages instead.

Rules shared by everything here:
* Only publicly visible people (Person.objects.public()) are ever returned.
* Every walk keeps a `seen` set and a depth limit, so even corrupt data that
  loops back on itself cannot recurse forever or list someone twice.
* Each relationship tier costs one query, never one query per relative.
"""
from django.db.models import Q

from .models import Person

MAX_FAMILY_MEMBERS = 3000


def _public():
    return Person.objects.public()


def _by_birth(people):
    def key(p):
        return (p.birth_year or '9999', p.last_name, p.first_name)
    return sorted(people, key=key)


def walk_ancestors(person, max_generations):
    """BFS upward from `person`. Returns (generations, truncated): a list
    (index 0 = parents) of lists of (Person, path) tuples, where path is the
    chain of 'Father'/'Mother' steps taken to reach them. De-duplicates by pk
    (a shared ancestor is shown once, at the generation first reached)."""
    generations = []
    visited = {person.pk}
    frontier = [(person, [])]
    truncated = False
    for gen in range(1, max_generations + 1):
        parent_ids = set()
        for p, _ in frontier:
            parent_ids.update(x for x in (p.father_id, p.mother_id) if x)
        parent_ids -= visited
        if not parent_ids:
            break
        people_map = {pp.pk: pp for pp in _public().filter(pk__in=parent_ids)}
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
            truncated = any((p.father_id and p.father_id not in visited) or
                            (p.mother_id and p.mother_id not in visited) for p, _ in frontier)
    return generations, truncated


def walk_descendants(person, max_generations):
    """BFS downward. Returns (generations, truncated): a list (index 0 =
    children) of lists of Person."""
    generations = []
    visited = {person.pk}
    frontier_ids = [person.pk]
    truncated = False
    for gen in range(1, max_generations + 1):
        children = list(_public().filter(Q(father_id__in=frontier_ids) | Q(mother_id__in=frontier_ids))
                        .exclude(pk__in=visited).distinct())
        if not children:
            break
        visited.update(c.pk for c in children)
        generations.append(_by_birth(children))
        frontier_ids = [c.pk for c in children]
        if gen == max_generations:
            truncated = _public().filter(Q(father_id__in=frontier_ids) | Q(mother_id__in=frontier_ids)) \
                .exclude(pk__in=visited).exists()
    return generations, truncated


def _gendered(gender, male, female, neutral):
    return {'M': male, 'F': female}.get(gender, neutral)


def _path_label(path, gender):
    """['Father', 'Mother', 'Father'] + M -> "Father's mother's father"."""
    words = [step.lower() for step in path[:-1]]
    last = _gendered(gender, 'father', 'mother', 'parent')
    text = "'s ".join(words + [last])
    return text[0].upper() + text[1:]


def _side(path):
    return 'Paternal' if path and path[0] == 'Father' else 'Maternal'


def _spouse_map(person_ids):
    """{person_id: [spouse Person, ...]} from verified, public marriages."""
    from apps.marriages.models import Marriage
    if not person_ids:
        return {}
    marriages = (Marriage.objects.public()
                 .filter(Q(husband_id__in=person_ids) | Q(wife_id__in=person_ids))
                 .select_related('husband', 'wife'))
    public_ids = set(_public().filter(
        pk__in={i for m in marriages for i in (m.husband_id, m.wife_id) if i}).values_list('pk', flat=True))
    out = {}
    for m in marriages:
        for me, other in ((m.husband, m.wife), (m.wife, m.husband)):
            if me and other and me.pk in person_ids and other.pk in public_ids:
                bucket = out.setdefault(me.pk, [])
                if other not in bucket:
                    bucket.append(other)
    return out


def _children_of(ids, exclude):
    if not ids:
        return []
    return _by_birth(_public().filter(Q(father_id__in=ids) | Q(mother_id__in=ids))
                     .exclude(pk__in=exclude).distinct())


def relatives_of(person):
    """Every recorded relative of `person`, grouped into labelled sections.

    Returns a list of {'key', 'title', 'entries': [{'person', 'label'}]}
    with empty sections left out, in the order they should be read.
    """
    sections = []
    listed = {person.pk}

    def add(key, title, entries):
        # Each person appears once, in the first (closest) section that
        # reaches them, even if bad data links them more than one way.
        entries = [e for e in entries if e['person'].pk not in listed]
        listed.update(e['person'].pk for e in entries)
        if entries:
            sections.append({'key': key, 'title': title, 'entries': entries, 'count': len(entries)})

    ancestors, _ = walk_ancestors(person, 4)
    parents = ancestors[0] if ancestors else []
    add('parents', 'Parents', [
        {'person': p, 'label': _gendered(p.gender, 'Father', 'Mother', 'Parent')} for p, _ in parents])
    add('grandparents', 'Grandparents', [
        {'person': p, 'label': f"{_side(path)} {_gendered(p.gender, 'grandfather', 'grandmother', 'grandparent')}"
                               f" ({_path_label(path, p.gender).lower()})"}
        for p, path in (ancestors[1] if len(ancestors) > 1 else [])])
    add('great_grandparents', 'Great-grandparents', [
        {'person': p, 'label': _path_label(path, p.gender)}
        for p, path in (ancestors[2] if len(ancestors) > 2 else [])])
    add('great_great_grandparents', 'Great-great-grandparents', [
        {'person': p, 'label': _path_label(path, p.gender)}
        for p, path in (ancestors[3] if len(ancestors) > 3 else [])])

    ancestor_ids = {p.pk for gen in ancestors for p, _ in gen}
    spouses = _spouse_map({person.pk}).get(person.pk, [])
    add('spouses', 'Husband / wife', [
        {'person': s, 'label': _gendered(s.gender, 'Husband', 'Wife', 'Spouse')} for s in spouses])

    # Siblings: full (same father and mother) and half (one parent shared).
    shown = {person.pk} | ancestor_ids | {s.pk for s in spouses}
    father_id, mother_id = person.father_id, person.mother_id
    sib_qs = Q()
    if father_id:
        sib_qs |= Q(father_id=father_id)
    if mother_id:
        sib_qs |= Q(mother_id=mother_id)
    siblings = _by_birth(_public().filter(sib_qs).exclude(pk__in=shown).distinct()) if sib_qs else []
    full, half = [], []
    for s in siblings:
        noun = _gendered(s.gender, 'brother', 'sister', 'sibling')
        if father_id and mother_id and s.father_id == father_id and s.mother_id == mother_id:
            full.append({'person': s, 'label': noun.capitalize()})
        else:
            via = 'father' if father_id and s.father_id == father_id else 'mother'
            half.append({'person': s, 'label': f'Half-{noun} (same {via})'})
    add('siblings', 'Brothers and sisters', full)
    add('half_siblings', 'Half-brothers and half-sisters', half)
    shown |= {s.pk for s in siblings}

    descendants, _ = walk_descendants(person, 4)
    child_words = [('children', 'Children', 'son', 'daughter', 'child'),
                   ('grandchildren', 'Grandchildren', 'grandson', 'granddaughter', 'grandchild'),
                   ('great_grandchildren', 'Great-grandchildren', 'great-grandson', 'great-granddaughter', 'great-grandchild'),
                   ('great_great_grandchildren', 'Great-great-grandchildren', 'great-great-grandson',
                    'great-great-granddaughter', 'great-great-grandchild')]
    for gen, (key, title, m, f, n) in zip(descendants, child_words):
        add(key, title, [{'person': c, 'label': _gendered(c.gender, m, f, n).capitalize()} for c in gen])
    shown |= {c.pk for gen in descendants for c in gen}

    # Uncles and aunts: children of grandparents other than the parents.
    grandparents = ancestors[1] if len(ancestors) > 1 else []
    gp_side = {}
    for gp, path in grandparents:
        gp_side.setdefault(gp.pk, _side(path).lower())
    aunts_uncles = _children_of(set(gp_side), shown)
    au_entries = []
    for au in aunts_uncles:
        side = gp_side.get(au.father_id) or gp_side.get(au.mother_id) or ''
        au_entries.append({'person': au, 'label': f"{_gendered(au.gender, 'Uncle', 'Aunt', 'Uncle/aunt')}"
                                                  f"{' (' + side + ')' if side else ''}"})
    add('aunts_uncles', 'Uncles and aunts', au_entries)
    shown |= {a.pk for a in aunts_uncles}

    au_by_id = {a.pk: a for a in aunts_uncles}
    cousins = _children_of(set(au_by_id), shown)
    add('cousins', 'First cousins', [
        {'person': c, 'label': f"Cousin, child of {(au_by_id.get(c.father_id) or au_by_id.get(c.mother_id)).first_name}"}
        for c in cousins])
    shown |= {c.pk for c in cousins}

    sib_by_id = {s.pk: s for s in siblings}
    nieces = _children_of(set(sib_by_id), shown)
    add('nieces_nephews', 'Nephews and nieces', [
        {'person': n, 'label': f"{_gendered(n.gender, 'Nephew', 'Niece', 'Nephew/niece')}, child of "
                               f"{(sib_by_id.get(n.father_id) or sib_by_id.get(n.mother_id)).first_name}"}
        for n in nieces])
    shown |= {n.pk for n in nieces}

    # In-laws: the spouse's parents and siblings, and the siblings' spouses.
    in_laws = []
    spouse_parent_ids = {x for s in spouses for x in (s.father_id, s.mother_id) if x} - shown
    for p in _by_birth(_public().filter(pk__in=spouse_parent_ids)):
        in_laws.append({'person': p, 'label': _gendered(p.gender, 'Father-in-law', 'Mother-in-law', 'Parent-in-law')})
    shown |= {e['person'].pk for e in in_laws}
    spouse_sib = _children_of(spouse_parent_ids, shown | {s.pk for s in spouses})
    for p in spouse_sib:
        in_laws.append({'person': p, 'label': _gendered(p.gender, 'Brother-in-law', 'Sister-in-law', 'Sibling-in-law')})
    shown |= {p.pk for p in spouse_sib}
    sib_spouses = _spouse_map(set(sib_by_id))
    for sib_id, partners in sib_spouses.items():
        for p in partners:
            if p.pk not in shown:
                shown.add(p.pk)
                in_laws.append({'person': p, 'label': f"{_gendered(p.gender, 'Brother-in-law', 'Sister-in-law', 'Sibling-in-law')}"
                                                      f" (married to {sib_by_id[sib_id].first_name})"})
    add('in_laws', 'In-laws', in_laws)
    return sections


def relatives_summary(person, sections):
    """A few plain sentences describing the person's family, for reading
    before the full lists."""
    by_key = {s['key']: s['entries'] for s in sections}
    subject = _gendered(person.gender, 'He', 'She', 'They')
    possessive = _gendered(person.gender, 'His', 'Her', 'Their')
    has = 'have' if subject == 'They' else 'has'

    def names(entries):
        return _join([e['person'].full_name for e in entries])

    out = []
    parents = by_key.get('parents', [])
    if parents:
        child = _gendered(person.gender, 'son', 'daughter', 'child')
        out.append(f"{person.full_name} is the {child} of {names(parents)}.")
    gps = by_key.get('grandparents', [])
    if gps:
        pat = [e for e in gps if e['label'].startswith('Paternal')]
        mat = [e for e in gps if e['label'].startswith('Maternal')]
        bits = []
        if pat:
            bits.append(f"{possessive.lower()} paternal grandparents are {names(pat)}")
        if mat:
            bits.append(f"{possessive.lower()} maternal grandparents are {names(mat)}")
        out.append(_cap('; '.join(bits)) + '.')
    ggp = by_key.get('great_grandparents', [])
    if ggp:
        out.append(f"{_count(len(ggp), 'great-grandparent')} {'is' if len(ggp) == 1 else 'are'} recorded.")
    spouses = by_key.get('spouses', [])
    if spouses:
        out.append(f"{subject} married {names(spouses)}.")
    full, half = by_key.get('siblings', []), by_key.get('half_siblings', [])
    if full or half:
        bits = []
        if full:
            bits.append(f"{_count(len(full), 'full sibling')}")
        if half:
            bits.append(f"{_count(len(half), 'half-sibling')}")
        out.append(f"{subject} {has} {' and '.join(bits)} in the archive.")
    kids = by_key.get('children', [])
    if kids:
        out.append(f"{subject} {has} {_count(len(kids), 'child', 'children')}: {names(kids)}.")
    for key, noun, plural in (('grandchildren', 'grandchild', 'grandchildren'),
                              ('great_grandchildren', 'great-grandchild', 'great-grandchildren')):
        if by_key.get(key):
            out.append(f"{subject} {has} {_count(len(by_key[key]), noun, plural)}.")
    others = [_count(len(by_key[k]), one, many) for k, one, many in (
        ('aunts_uncles', 'uncle or aunt', 'uncles and aunts'),
        ('cousins', 'first cousin', 'first cousins'),
        ('nieces_nephews', 'nephew or niece', 'nephews and nieces'),
        ('in_laws', 'in-law', 'in-laws')) if by_key.get(k)]
    if others:
        out.append(f"The archive also records {_join(others)}.")
    if not out:
        out.append(f"No relatives of {person.full_name} are recorded in the archive yet.")
    return out


def _count(n, noun, plural=None):
    return f"{n} {noun if n == 1 else (plural or noun + 's')}"


def _join(items):
    items = list(items)
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def _cap(text):
    return text[:1].upper() + text[1:]


# ── A family, generation by generation ────────────────────────────────────

ORDINALS = ['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth', 'Ninth', 'Tenth']


def family_generations(family):
    """The family's public members arranged by generation.

    Returns a list of {'number', 'title', 'entries'}; each entry is
    {'person', 'parents', 'spouses', 'children', 'married_in'}. Founders are
    members with no parent in the family; people who married into the
    family are placed in their spouse's generation.
    """
    members = list(family.person_set.public().order_by('birth_year', 'last_name', 'first_name')[:MAX_FAMILY_MEMBERS])
    if not members:
        return []
    by_id = {p.pk: p for p in members}
    ids = set(by_id)
    spouses = _spouse_map(ids)

    children = {pid: [] for pid in ids}
    for p in members:
        for parent_id in {p.father_id, p.mother_id} - {None}:
            if parent_id in ids:
                children[parent_id].append(p)

    has_parent_in_family = {p.pk for p in members if (p.father_id in ids) or (p.mother_id in ids)}
    # Married-in: no parents in the family, but married to someone who has.
    married_in = {p.pk for p in members
                  if p.pk not in has_parent_in_family
                  and any(s.pk in has_parent_in_family for s in spouses.get(p.pk, []))}
    roots = [p for p in members if p.pk not in has_parent_in_family and p.pk not in married_in]

    generation = {}
    frontier = [r.pk for r in roots]
    depth = 0
    while frontier and depth < len(ORDINALS) * 5:
        nxt = []
        for pid in frontier:
            if pid in generation:
                continue
            generation[pid] = depth
            nxt += [c.pk for c in children.get(pid, []) if c.pk not in generation]
        frontier = nxt
        depth += 1
    for pid in married_in:
        partner_gens = [generation[s.pk] for s in spouses.get(pid, []) if s.pk in generation]
        generation[pid] = min(partner_gens) if partner_gens else 0
    for p in members:  # anything unreachable (bad data) goes with the founders
        generation.setdefault(p.pk, 0)

    rows = {}
    for p in members:
        rows.setdefault(generation[p.pk], []).append({
            'person': p,
            'parents': [by_id[i] for i in (p.father_id, p.mother_id) if i in by_id],
            'spouses': spouses.get(p.pk, []),
            'children': _by_birth(children.get(p.pk, [])),
            'married_in': p.pk in married_in,
        })
    out = []
    for n in sorted(rows):
        title = f'{ORDINALS[n]} generation' if n < len(ORDINALS) else f'Generation {n + 1}'
        entries = sorted(rows[n], key=lambda e: (e['married_in'], e['person'].birth_year or '9999'))
        out.append({'number': n + 1, 'title': title, 'entries': entries})
    return out
