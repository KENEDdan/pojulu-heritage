"""Phase 7: no N+1 queries, pagination, dashboard filters, caching, indexes."""
import datetime

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.achievements.models import Achievement
from apps.clans.models import Clan, ClanChief
from apps.cultural.models import CulturalRecord
from apps.elders.models import ElderInterview
from apps.genealogy.models import Family, Person
from apps.marriages.models import Marriage
from apps.memorial.models import MemorialRecord
from apps.news.models import NewsPost

_n = {'i': 0}


def add_rows(n):
    """n more published rows of everything, each linked to its own clan."""
    for _ in range(n):
        _n['i'] += 1
        i = _n['i']
        clan = Clan.objects.create(name=f'Clan{i}', payam='kupera', description='d', is_verified=True, is_featured=True)
        ClanChief.objects.create(clan=clan, name=f'Chief{i}')
        fam = Family.objects.create(name=f'Fam{i}', clan=clan, is_verified=True)
        dad = Person.objects.create(first_name=f'Dad{i}', last_name='X', clan=clan, family=fam, is_verified=True,
                                    is_deceased=True, gender='M')
        Person.objects.create(first_name=f'Kid{i}', last_name='X', clan=clan, family=fam, father=dad, is_verified=True)
        MemorialRecord.objects.create(person=dad, tribute='t')
        Marriage.objects.create(husband=dad, husband_clan=clan, wife_name='W', is_verified=True)
        Achievement.objects.create(person_name='P', person=dad, clan=clan, category='other', title='T',
                                   description='d', is_verified=True, is_featured=True)
        CulturalRecord.objects.create(title=f'Song{i}', record_type='song', content='c', clan=clan, is_verified=True)
        ElderInterview.objects.create(elder_name=f'E{i}', interviewer='K', summary='s', clan=clan,
                                      is_published=True, interview_date=datetime.date(2020, 1, 1))
        NewsPost.objects.create(title=f'News{i}', excerpt='e', content='c', is_published=True)


def queries(client, url):
    cache.clear()
    with CaptureQueriesContext(connection) as ctx:
        r = client.get(url)
    assert r.status_code == 200, url
    return len(ctx.captured_queries)


PUBLIC_LISTS = ['core:home', 'clans:list', 'genealogy:list', 'memorial:list', 'achievements:list',
                'marriages:list', 'cultural:list', 'elders:list', 'news:list']


@pytest.mark.django_db
@pytest.mark.parametrize('name', PUBLIC_LISTS)
def test_public_list_query_count_does_not_grow_with_rows(client, name):
    add_rows(2)
    small = queries(client, reverse(name))
    add_rows(6)
    large = queries(client, reverse(name))
    # More rows must never mean more queries (fewer is fine: some empty-state
    # fallbacks only run when there is little data).
    assert large <= small, f'{name}: {small} queries for 2 rows, {large} for 8 (N+1)'


@pytest.mark.django_db
def test_search_query_count_is_constant(client):
    add_rows(2)
    small = queries(client, reverse('core:search') + '?q=X')
    add_rows(6)
    assert queries(client, reverse('core:search') + '?q=X') == small


@pytest.mark.django_db
def test_clan_detail_query_count_is_constant(client):
    add_rows(1)
    clan = Clan.objects.get(name='Clan' + str(_n['i']))
    small = queries(client, clan.get_absolute_url())
    for j in range(8):
        f = Family.objects.create(name=f'Extra{j}{_n["i"]}', clan=clan, is_verified=True)
        Person.objects.create(first_name=f'Extra{j}', last_name='Y', clan=clan, family=f, is_verified=True)
    assert queries(client, clan.get_absolute_url()) == small


@pytest.mark.parametrize('name', ['clan_dashboard', 'genealogy_dashboard', 'memorial_dashboard', 'cultural_dashboard',
                                  'elder_dashboard', 'achievement_dashboard', 'news_dashboard'])
def test_dashboard_query_count_does_not_grow_with_rows(client, superadmin, name):
    client.force_login(superadmin)
    add_rows(2)
    small = queries(client, reverse(f'dashboard:{name}'))
    add_rows(6)
    large = queries(client, reverse(f'dashboard:{name}'))
    assert large == small, f'{name}: {small} vs {large}'


def test_clan_counts_are_annotated_and_respect_visibility(db):
    add_rows(1)
    clan = Clan.objects.public().with_counts().get(name='Clan' + str(_n['i']))
    Person.objects.create(first_name='Hidden', last_name='Z', clan=clan, is_verified=True, is_private=True)
    Person.objects.create(first_name='Unverified', last_name='Z', clan=clan)
    clan = Clan.objects.public().with_counts().get(pk=clan.pk)
    assert clan.person_count == 2 and clan.family_count == 1
    assert clan.person_count == clan.person_set.public().count()


# ── pagination & filters ─────────────────────────────────────────────────────

def test_dashboard_tables_paginate_at_25(client, superadmin, db):
    client.force_login(superadmin)
    for i in range(30):
        Person.objects.create(first_name=f'P{i:02d}', last_name='Pag')
    r = client.get(reverse('dashboard:genealogy_dashboard'))
    assert len(r.context['persons'].object_list) == 25
    r2 = client.get(reverse('dashboard:genealogy_dashboard'), {'page': 2})
    assert len(r2.context['persons'].object_list) == 5
    assert 'Page 2 of 2' in r2.content.decode()


def test_public_lists_paginate_at_25(client, db):
    clan = Clan.objects.create(name='Big', payam='kupera', description='d', is_verified=True)
    for i in range(30):
        Family.objects.create(name=f'F{i:02d}', clan=clan, is_verified=True)
    r = client.get(reverse('genealogy:list'))
    assert len(r.context['families']) == 25
    assert 'page=2' in r.content.decode()


def test_genealogy_dashboard_filters(client, superadmin, world):
    client.force_login(superadmin)
    url = reverse('dashboard:genealogy_dashboard')
    names = lambda r: {p.first_name for p in r.context['persons']}
    assert names(client.get(url, {'q': 'juma'})) == {'Juma'}
    assert 'Draft' in names(client.get(url, {'status': 'draft'}))
    assert 'Draft' not in names(client.get(url, {'status': 'published'}))
    other = Clan.objects.create(name='Other', payam='kupera', description='d')
    Person.objects.create(first_name='Elsewhere', last_name='Q', clan=other)
    assert names(client.get(url, {'clan': other.pk})) == {'Elsewhere'}
    fams = {f.name for f in client.get(url, {'q': 'secret'}).context['families']}
    assert fams == {'Secret Family'}


@pytest.mark.parametrize('name,params,expect', [
    ('clan_dashboard', {'q': 'gum'}, 'Gumbo'),
    ('elder_dashboard', {'status': 'draft'}, 'Draft Elder'),
    ('news_dashboard', {'q': 'launch'}, 'Launch'),
])
def test_other_dashboard_filters(client, superadmin, world, name, params, expect):
    client.force_login(superadmin)
    html = client.get(reverse(f'dashboard:{name}'), params).content.decode()
    assert expect in html


def test_pagination_keeps_filters(client, superadmin, db):
    client.force_login(superadmin)
    for i in range(30):
        Person.objects.create(first_name=f'Keep{i:02d}', last_name='Filter')
    html = client.get(reverse('dashboard:genealogy_dashboard'), {'q': 'keep'}).content.decode()
    assert '?q=keep&amp;page=2' in html


# ── caching ──────────────────────────────────────────────────────────────────

def test_home_stats_and_news_are_cached(client, world):
    cache.clear()
    with CaptureQueriesContext(connection) as first:
        client.get(reverse('core:home'))
    with CaptureQueriesContext(connection) as second:
        r = client.get(reverse('core:home'))
    assert len(second.captured_queries) < len(first.captured_queries)
    assert r.context['stats']['persons'] >= 1
    assert r.context['featured_post'] is None or r.context['featured_post'].is_published


def test_indexes_declared():
    names = {i.name for i in Person._meta.indexes}
    assert {'person_name_idx', 'person_visible_idx'} <= names
    assert 'news_published_idx' in {i.name for i in NewsPost._meta.indexes}
    assert 'interview_published_idx' in {i.name for i in ElderInterview._meta.indexes}
    for model, field in [(Person, 'clan'), (Person, 'family'), (Person, 'father'), (Person, 'mother'),
                         (Marriage, 'husband'), (Marriage, 'wife')]:
        assert model._meta.get_field(field).db_index
    assert Clan._meta.get_field('slug').unique and Family._meta.get_field('slug').unique
