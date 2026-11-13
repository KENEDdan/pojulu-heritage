"""Written family histories, complete relatives lists, clan territory and
landmarks, full chief histories, and photos/evidence on every record."""
import io
import json

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.clans.models import ClanChief, ClanLandmark, validate_boundary_geojson
from apps.core.models import Attachment
from apps.genealogy.models import Family, FamilyHistoryChapter, Person
from apps.genealogy.relatives import family_generations, relatives_of, relatives_summary
from apps.marriages.models import Marriage
from tests.conftest import make_staff

pytestmark = pytest.mark.django_db


def png():
    out = io.BytesIO()
    Image.new('RGB', (40, 30), (0, 120, 0)).save(out, 'PNG')
    return out.getvalue()


def P(first, gender='M', **kw):
    kw.setdefault('is_verified', True)
    return Person.objects.create(first_name=first, last_name='T', gender=gender, **kw)


@pytest.fixture
def kin(world):
    """Four generations above `me`, full and half siblings, an uncle with a
    child, a nephew, a spouse with parents, and one private living cousin."""
    fam = world['family']
    g = {}
    for side in ('ff', 'fm', 'mf', 'mm'):          # great-grandparents (8)
        g[side + 'f'] = P(side + 'f', 'M')
        g[side + 'm'] = P(side + 'm', 'F')
    g['ff'] = P('ff', 'M', father=g['fff'], mother=g['ffm'], family=fam)   # grandparents (4)
    g['fm'] = P('fm', 'F', father=g['fmf'], mother=g['fmm'])
    g['mf'] = P('mf', 'M', father=g['mff'], mother=g['mfm'])
    g['mm'] = P('mm', 'F', father=g['mmf'], mother=g['mmm'])
    g['dad'] = P('Dad', 'M', father=g['ff'], mother=g['fm'], family=fam)
    g['mum'] = P('Mum', 'F', father=g['mf'], mother=g['mm'])
    g['uncle'] = P('Uncle', 'M', father=g['ff'], mother=g['fm'], family=fam)
    g['cousin'] = P('Cousin', 'F', father=g['uncle'], family=fam)
    g['hidden_cousin'] = P('Hiddencousin', 'M', father=g['uncle'], is_private=True)
    g['me'] = P('Me', 'M', father=g['dad'], mother=g['mum'], family=fam)
    g['sis'] = P('Sis', 'F', father=g['dad'], mother=g['mum'], family=fam)
    g['halfbro'] = P('Halfbro', 'M', father=g['dad'], family=fam)
    g['nephew'] = P('Nephew', 'M', mother=g['sis'], family=fam)
    g['wife'] = P('Wife', 'F', father=P('Wifedad', 'M'), mother=P('Wifemum', 'F'))
    g['son'] = P('Son', 'M', father=g['me'], mother=g['wife'], family=fam)
    Marriage.objects.create(husband=g['me'], wife=g['wife'], is_verified=True)
    Marriage.objects.create(husband=g['ff'], wife=g['fm'], is_verified=True)
    return g


def section(sections, key):
    return next((s for s in sections if s['key'] == key), {'entries': []})


def names(sections, key):
    return sorted(e['person'].first_name for e in section(sections, key)['entries'])


# ── relatives list ───────────────────────────────────────────────────────────

def test_relatives_lists_every_tier(kin):
    s = relatives_of(kin['me'])
    assert names(s, 'parents') == ['Dad', 'Mum']
    assert names(s, 'grandparents') == ['ff', 'fm', 'mf', 'mm']
    assert len(section(s, 'great_grandparents')['entries']) == 8
    assert names(s, 'siblings') == ['Sis']
    assert names(s, 'half_siblings') == ['Halfbro']
    assert names(s, 'spouses') == ['Wife']
    assert names(s, 'children') == ['Son']
    assert names(s, 'aunts_uncles') == ['Uncle']
    assert names(s, 'cousins') == ['Cousin']
    assert names(s, 'nieces_nephews') == ['Nephew']
    assert names(s, 'in_laws') == ['Wifedad', 'Wifemum']


def test_relatives_labels_say_which_side(kin):
    labels = {e['person'].first_name: e['label'] for e in section(relatives_of(kin['me']), 'grandparents')['entries']}
    assert labels['ff'].startswith('Paternal grandfather')
    assert labels['mm'].startswith('Maternal grandmother')
    ggp = {e['person'].first_name: e['label'] for e in section(relatives_of(kin['me']), 'great_grandparents')['entries']}
    assert ggp['fmf'] == "Father's mother's father"


def test_relatives_never_include_private_or_unverified(kin, world):
    P('Draftsis', 'F', father=kin['dad'], is_verified=False)
    every = {e['person'].first_name for sec in relatives_of(kin['me']) for e in sec['entries']}
    assert 'Hiddencousin' not in every and 'Draftsis' not in every


def test_relatives_summary_reads_naturally(kin):
    text = ' '.join(relatives_summary(kin['me'], relatives_of(kin['me'])))
    assert 'Me T is the son of Dad T and Mum T.' in text
    assert 'paternal grandparents are' in text and 'maternal grandparents are' in text
    assert '1 full sibling and 1 half-sibling' in text


def test_relatives_survive_a_parent_cycle(kin):
    # Bypass clean() to plant corrupt data: grandfather recorded as his grandson's son.
    Person.objects.filter(pk=kin['ff'].pk).update(father=kin['me'])
    sections = relatives_of(kin['me'])   # must terminate
    every = [e['person'].pk for sec in sections for e in sec['entries']]
    assert len(every) == len(set(every)), 'nobody is listed twice'


def test_relatives_query_count_is_bounded(kin, django_assert_max_num_queries):
    with django_assert_max_num_queries(25):
        relatives_of(kin['me'])


# ── family written history ───────────────────────────────────────────────────

def test_family_generations_orders_people_and_places_spouses(kin, world):
    fam = world['family']
    kin['wife'].family = fam
    kin['wife'].save()
    gens = family_generations(fam)
    by_name = {e['person'].first_name: (g['number'], e) for g in gens for e in g['entries']}
    assert by_name['ff'][0] < by_name['Dad'][0] < by_name['Me'][0] < by_name['Son'][0]
    assert by_name['Wife'][0] == by_name['Me'][0] and by_name['Wife'][1]['married_in']
    assert {c.first_name for c in by_name['Dad'][1]['children']} == {'Me', 'Sis', 'Halfbro'}
    assert 'Hiddencousin' not in by_name


def test_family_page_shows_written_history_chapters_and_generations(client, kin, world):
    fam = world['family']
    fam.written_history = 'The Ladu family began at the river.'
    fam.save()
    FamilyHistoryChapter.objects.create(family=fam, title='Exile and return', period='1990-2005', body='They walked south.')
    html = client.get(fam.get_absolute_url()).content.decode()
    assert 'The Ladu family began at the river.' in html
    assert 'Exile and return' in html and 'They walked south.' in html
    assert 'Generation by Generation' in html and 'First generation' in html
    assert 'Hiddencousin' not in html


def test_person_page_lists_all_relatives_and_notes(client, kin):
    me = kin['me']
    me.relatives_notes = 'He also has eleven brothers in Yei who are not yet recorded.'
    me.save()
    html = client.get(me.get_absolute_url()).content.decode()
    assert 'All Relatives' in html
    for name in ('fmf T', 'Halfbro T', 'Cousin T', 'Nephew T', 'Wifedad T'):
        assert name in html
    assert 'eleven brothers in Yei' in html
    assert 'Hiddencousin' not in html


# ── clans: territory, map, landmarks ─────────────────────────────────────────

SQUARE = {'type': 'Polygon', 'coordinates': [[[30.9, 4.3], [31.0, 4.3], [31.0, 4.4], [30.9, 4.4], [30.9, 4.3]]]}


@pytest.mark.parametrize('value', [
    json.dumps(SQUARE),
    json.dumps({'type': 'Feature', 'geometry': SQUARE, 'properties': {}}),
    json.dumps({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': SQUARE}]}),
    json.dumps({'type': 'MultiPolygon', 'coordinates': [SQUARE['coordinates']]}),
])
def test_boundary_accepts_polygons(value):
    validate_boundary_geojson(value)


@pytest.mark.parametrize('value', [
    'not json',
    json.dumps({'type': 'LineString', 'coordinates': [[30, 4], [31, 4]]}),
    json.dumps({'type': 'Polygon', 'coordinates': [[[30, 4], [31, 4], [30, 4]]]}),          # too few points
    json.dumps({'type': 'Polygon', 'coordinates': [[[300, 4], [31, 4], [31, 5], [300, 4]]]}),  # out of range
    json.dumps({'type': 'Polygon', 'coordinates': [[["<script>", 4], [31, 4], [31, 5], [30, 4]]]}),
    json.dumps({'type': 'FeatureCollection', 'features': []}),
])
def test_boundary_rejects_everything_else(value):
    with pytest.raises(ValidationError):
        validate_boundary_geojson(value)


def test_landmark_needs_both_coordinates(world):
    lm = ClanLandmark(clan=world['clan'], name='X', description='d', latitude=4.3)
    with pytest.raises(ValidationError):
        lm.full_clean()


def test_clan_page_shows_territory_map_landmarks_and_chiefs(client, world):
    clan = world['clan']
    clan.boundary_geojson = json.dumps(SQUARE)
    clan.territory_description = 'From the river to the granite hills.'
    clan.border_north = 'Wuji forest'
    clan.save()
    html = client.get(clan.get_absolute_url()).content.decode()
    assert 'Territory &amp; Map' in html and 'From the river to the granite hills.' in html
    assert 'Wuji forest' in html
    assert 'id="clan-map-data"' in html and '30.9' in html and 'Gumbo Hill' in html
    assert world['chief'].get_absolute_url() in html
    assert 'leaflet' in html


def test_clan_page_without_map_does_not_load_leaflet(client, world):
    world['landmark'].delete()
    html = client.get(world['clan'].get_absolute_url()).content.decode()
    assert 'leaflet' not in html


# ── chiefs ───────────────────────────────────────────────────────────────────

def test_chief_page_shows_full_history_and_succession(client, world):
    first = world['chief']
    first.biography = 'Born under the tamarind tree.'
    first.accomplishments = 'Built the first school.'
    first.order = 0
    first.save()
    second = ClanChief.objects.create(clan=world['clan'], name='Wani', order=1, legacy='Remembered for peace.')
    html = client.get(first.get_absolute_url()).content.decode()
    assert 'Born under the tamarind tree.' in html and 'Built the first school.' in html
    assert second.get_absolute_url() in html and 'Succeeded by' in html
    html2 = client.get(second.get_absolute_url()).content.decode()
    assert 'Remembered for peace.' in html2 and 'Preceded by' in html2


def test_chief_page_404_for_draft_clan_or_wrong_clan(client, world):
    hidden = ClanChief.objects.create(clan=world['clan_draft'], name='Secret')
    assert client.get(hidden.get_absolute_url()).status_code == 404
    wrong = reverse('clans:chief_detail', kwargs={'slug': world['clan'].slug, 'pk': hidden.pk})
    assert client.get(wrong).status_code == 404


def test_chief_page_links_person_only_when_public(client, world):
    chief = world['chief']
    chief.person = world['person_draft']
    chief.save()
    assert world['person_draft'].get_absolute_url() not in client.get(chief.get_absolute_url()).content.decode()
    chief.person = world['person']
    chief.save()
    assert world['person'].get_absolute_url() in client.get(chief.get_absolute_url()).content.decode()


def test_sitemap_lists_public_chiefs_only(client, world):
    hidden = ClanChief.objects.create(clan=world['clan_draft'], name='Secret')
    xml = client.get('/sitemap.xml').content.decode()
    assert world['chief'].get_absolute_url() in xml
    assert hidden.get_absolute_url() not in xml


# ── photos & evidence ────────────────────────────────────────────────────────

def attach(record, title, is_public=True, data=None, name='photo.png'):
    return Attachment.objects.create(
        content_type=ContentType.objects.get_for_model(record), object_id=record.pk, title=title,
        is_public=is_public, file=SimpleUploadedFile(name, data or png()))


def test_public_evidence_shown_private_evidence_hidden(client, world):
    fam = world['family']
    attach(fam, 'Wedding photo 1962')
    attach(fam, 'Land dispute letter', is_public=False)
    html = client.get(fam.get_absolute_url()).content.decode()
    assert 'Wedding photo 1962' in html
    assert 'Land dispute letter' not in html


def test_evidence_files_go_through_the_gate(client, world):
    public = attach(world['family'], 'Public')
    private = attach(world['family'], 'Private', is_public=False)
    on_draft = attach(world['family_draft'], 'Draft family photo')
    assert public.file.url.startswith('/private-media/')
    assert client.get(public.file.url).status_code == 200
    assert client.get(private.file.url).status_code == 404
    assert client.get(on_draft.file.url).status_code == 404


def test_evidence_staff_access_follows_role_sections(client, world):
    private = attach(world['family'], 'Private', is_public=False)
    client.force_login(make_staff('clan_admin'))
    assert client.get(private.file.url).status_code == 404
    client.force_login(make_staff('genealogy_admin'))
    assert client.get(private.file.url).status_code == 200


def test_evidence_on_landmarks_and_chiefs_follows_their_clan(client, world):
    lm_photo = attach(world['landmark'], 'Hill photo')
    hidden_chief = ClanChief.objects.create(clan=world['clan_draft'], name='Secret')
    chief_photo = attach(hidden_chief, 'Secret chief photo')
    assert client.get(lm_photo.file.url).status_code == 200
    assert client.get(chief_photo.file.url).status_code == 404


def test_evidence_image_is_sanitised_and_renamed(world):
    att = attach(world['family'], 'x', name='../../evil name.png')
    assert att.file.name.startswith('attachments/') and 'evil' not in att.file.name


def _mgmt(prefix, total=0, initial=0):
    return {f'{prefix}-TOTAL_FORMS': str(total), f'{prefix}-INITIAL_FORMS': str(initial),
            f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000'}


def test_dashboard_family_form_saves_chapters_and_evidence(client, superadmin, world):
    client.force_login(superadmin)
    fam = world['family']
    data = {'name': fam.name, 'clan': fam.clan_id, 'payam': '', 'origin_village': '', 'description': '',
            'written_history': 'Our story.', 'is_verified': 'on',
            **_mgmt('chapters', 1), 'chapters-0-title': 'Origins', 'chapters-0-period': '', 'chapters-0-order': '0',
            'chapters-0-body': 'At the river.',
            **_mgmt('evidence', 1), 'evidence-0-kind': 'photo', 'evidence-0-title': 'Old photo',
            'evidence-0-is_public': 'on', 'evidence-0-file': SimpleUploadedFile('old.png', png())}
    r = client.post(reverse('dashboard:family_edit', args=[fam.pk]), data)
    assert r.status_code == 302, r.content.decode()[:3000]
    fam.refresh_from_db()
    assert fam.written_history == 'Our story.'
    assert fam.chapters.get().title == 'Origins'
    assert fam.attachments.get().title == 'Old photo'


def test_dashboard_evidence_rejects_disguised_executable(client, superadmin, world):
    client.force_login(superadmin)
    chief = world['chief']
    data = {'clan': chief.clan_id, 'name': chief.name, 'title': 'Chief', 'order': '0',
            **_mgmt('evidence', 1), 'evidence-0-kind': 'photo', 'evidence-0-title': 'x', 'evidence-0-is_public': 'on',
            'evidence-0-file': SimpleUploadedFile('photo.jpg', b'MZ\x90\x00 this is an exe')}
    r = client.post(reverse('dashboard:chief_edit', args=[chief.pk]), data)
    assert r.status_code == 200
    assert not chief.attachments.exists()


def test_dashboard_evidence_row_needs_a_file_or_link(client, superadmin, world):
    client.force_login(superadmin)
    chief = world['chief']
    data = {'clan': chief.clan_id, 'name': chief.name, 'title': 'Chief', 'order': '0',
            **_mgmt('evidence', 1), 'evidence-0-kind': 'document', 'evidence-0-title': 'Letter',
            'evidence-0-is_public': 'on'}
    r = client.post(reverse('dashboard:chief_edit', args=[chief.pk]), data)
    assert r.status_code == 200 and 'Upload a file or give a link.' in r.content.decode()


def test_empty_evidence_rows_are_ignored(client, superadmin, world):
    client.force_login(superadmin)
    chief = world['chief']
    data = {'clan': chief.clan_id, 'name': 'Lado Renamed', 'title': 'Chief', 'order': '0',
            'biography': 'A long life.', **_mgmt('evidence', 2),
            'evidence-0-kind': 'photo', 'evidence-0-is_public': 'on',
            'evidence-1-kind': 'photo', 'evidence-1-is_public': 'on'}
    r = client.post(reverse('dashboard:chief_edit', args=[chief.pk]), data)
    assert r.status_code == 302
    chief.refresh_from_db()
    assert chief.name == 'Lado Renamed' and chief.biography == 'A long life.'


@pytest.mark.parametrize('url_name,kwargs_key', [
    ('memorial_edit', 'memorial'), ('achievement_edit', 'achievement'), ('marriage_edit', 'marriage'),
    ('cultural_edit', 'cultural'), ('elder_edit', 'interview'), ('event_edit', 'event'),
    ('landmark_edit', 'landmark'), ('chief_edit', 'chief'), ('family_edit', 'family'),
])
def test_every_record_form_has_an_evidence_section(client, superadmin, world, url_name, kwargs_key):
    client.force_login(superadmin)
    html = client.get(reverse(f'dashboard:{url_name}', args=[world[kwargs_key].pk])).content.decode()
    main_form = html.split('<form method="post" enctype="multipart/form-data"', 1)[1].split('</form>', 1)[0]
    assert 'evidence-TOTAL_FORMS' in main_form and 'Photos &amp; Evidence' in html


# ── landmark permissions ─────────────────────────────────────────────────────

def test_landmark_permissions(client, world):
    client.force_login(make_staff('clan_admin'))
    assert client.get(reverse('dashboard:landmark_add')).status_code == 200
    assert client.post(reverse('dashboard:landmark_delete', args=[world['landmark'].pk])).status_code == 302
    assert ClanLandmark.objects.filter(pk=world['landmark'].pk).exists(), 'only superadmin may delete'
    client.force_login(make_staff('genealogy_admin'))
    r = client.get(reverse('dashboard:landmark_add'))
    assert r.status_code == 302 and 'landmarks' not in r['Location']


def test_superadmin_deletes_landmark_by_post_only(client, superadmin, world):
    client.force_login(superadmin)
    url = reverse('dashboard:landmark_delete', args=[world['landmark'].pk])
    assert client.get(url).status_code == 405
    client.post(url)
    assert not ClanLandmark.objects.filter(pk=world['landmark'].pk).exists()


def test_clan_form_saves_boundary_drawn_on_map(client, superadmin, world):
    client.force_login(superadmin)
    clan = world['clan']
    data = {'name': clan.name, 'payam': clan.payam, 'description': 'x', 'is_verified': 'on',
            'boundary_geojson': json.dumps(SQUARE), **_mgmt('media_files')}
    r = client.post(reverse('dashboard:clan_edit', args=[clan.pk]), data)
    assert r.status_code == 302
    clan.refresh_from_db()
    assert json.loads(clan.boundary_geojson) == SQUARE
    data['boundary_geojson'] = '{"type": "Point", "coordinates": [30, 4]}'
    r = client.post(reverse('dashboard:clan_edit', args=[clan.pk]), data)
    assert r.status_code == 200 and 'must be a polygon' in r.content.decode()


def test_family_soft_delete_still_works_with_relations(client, superadmin, world):
    client.force_login(superadmin)
    attach(world['family'], 'Kept photo')
    client.post(reverse('dashboard:family_delete', args=[world['family'].pk]))
    assert Family.all_objects.get(pk=world['family'].pk).is_deleted
    assert Attachment.objects.filter(title='Kept photo').exists(), 'evidence survives a move to the Trash'
