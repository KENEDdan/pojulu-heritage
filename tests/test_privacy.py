"""Phase 4: public visibility, privacy of living people, private media."""
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.genealogy.models import Person
from apps.marriages.models import Marriage
from tests.conftest import make_staff

ROOT = Path(__file__).resolve().parent.parent

PUBLIC_PAGES = ['core:home', 'core:about', 'clans:list', 'genealogy:list', 'memorial:list',
                'achievements:list', 'marriages:list', 'cultural:list', 'elders:list', 'news:list']


def detail_url(obj):
    return obj.get_absolute_url()


# ── unpublished records ──────────────────────────────────────────────────────

@pytest.mark.parametrize('key', ['clan', 'family', 'person', 'memorial', 'achievement', 'marriage',
                                 'cultural', 'interview', 'news'])
def test_published_detail_pages_render(client, world, key):
    assert client.get(detail_url(world[key])).status_code == 200


@pytest.mark.parametrize('key', ['clan_draft', 'family_draft', 'person_draft', 'memorial_draft',
                                 'achievement_draft', 'marriage_draft', 'cultural_draft',
                                 'interview_draft', 'news_draft'])
def test_unpublished_detail_pages_404(client, world, key):
    assert client.get(detail_url(world[key])).status_code == 404


def test_unpublished_person_tree_404(client, world):
    assert client.get(reverse('genealogy:tree', args=[world['person_draft'].slug])).status_code == 404


@pytest.mark.parametrize('page', PUBLIC_PAGES)
def test_lists_never_show_unpublished_names(client, world, page):
    html = client.get(reverse(page)).content.decode()
    for secret in ['Hidden Clan', 'Secret Family', 'Draft Person', 'Secret award', 'Draft song',
                   'Draft Elder', 'Draft news', 'Not public']:
        assert secret not in html, (page, secret)


def test_search_never_returns_unpublished(client, world):
    for q in ['Draft', 'Secret', 'Hidden']:
        html = client.get(reverse('core:search'), {'q': q}).content.decode()
        assert 'Draft Person' not in html and 'Secret Family' not in html and 'Draft news' not in html


def test_unverified_relatives_not_shown_on_person_page(client, world):
    # person_draft is an unverified child of `father`
    html = client.get(detail_url(world['father'])).content.decode()
    assert 'Juma' in html          # verified child shown
    assert 'Draft Person' not in html


def test_marriage_linking_hidden_person_is_not_public(client, world):
    m = Marriage.objects.create(husband=world['person_draft'], wife_name='Someone', year='2001', is_verified=True)
    assert client.get(m.get_absolute_url()).status_code == 404
    assert 'Draft Person' not in client.get(reverse('marriages:list')).content.decode()


# ── contact details ──────────────────────────────────────────────────────────

CONTACT = ['+211 900 000 111', 'juma@example.org', 'Hidden Street']


def _public_pages_for(client, person):
    urls = [detail_url(person), reverse('genealogy:tree', args=[person.slug]),
            detail_url(person.family), detail_url(person.clan),
            reverse('core:search') + '?q=Juma', reverse('core:home')]
    return [client.get(u).content.decode() for u in urls]


def test_contact_details_hidden_by_default(client, world):
    for html in _public_pages_for(client, world['person']):
        for value in CONTACT:
            assert value not in html


def test_contact_details_shown_only_with_consent(client, world):
    p = world['person']
    p.show_contact_publicly = True
    p.save()
    html = client.get(detail_url(p)).content.decode()
    for value in CONTACT:
        assert value in html
    # ... and still nowhere else.
    for other in _public_pages_for(client, p)[1:]:
        for value in CONTACT:
            assert value not in other


def test_staff_dashboard_always_sees_contact_details(client, superadmin, world):
    client.force_login(superadmin)
    html = client.get(reverse('dashboard:person_edit', args=[world['person'].pk])).content.decode()
    assert '+211 900 000 111' in html and 'juma@example.org' in html


# ── is_private ───────────────────────────────────────────────────────────────

def test_private_living_person_hidden_everywhere(client, world):
    p = world['person']
    p.is_private = True
    p.save()
    assert client.get(detail_url(p)).status_code == 404
    assert client.get(reverse('genealogy:tree', args=[p.slug])).status_code == 404
    for url in [detail_url(world['father']), reverse('genealogy:tree', args=[world['father'].slug]),
                detail_url(world['family']), detail_url(world['clan']), reverse('core:home'),
                reverse('core:search') + '?q=Juma']:
        assert 'Juma Ladu' not in client.get(url).content.decode(), url


def test_private_flag_does_not_hide_deceased(client, world):
    f = world['father']
    f.is_private = True
    f.save()
    assert client.get(detail_url(f)).status_code == 200


def test_public_queryset_rules(world):
    ids = set(Person.objects.public().values_list('pk', flat=True))
    assert world['person'].pk in ids and world['person_draft'].pk not in ids


# ── private media ────────────────────────────────────────────────────────────

PDF = b'%PDF-1.4\nprivate profile'


@pytest.fixture
def private_pdf(world):
    p = world['person']
    p.profile_pdf = SimpleUploadedFile('profile.pdf', PDF)
    p.save()
    return p


def test_private_file_is_stored_outside_media_root(private_pdf, settings):
    path = Path(private_pdf.profile_pdf.storage.path(private_pdf.profile_pdf.name))
    assert Path(settings.PRIVATE_MEDIA_ROOT) in path.parents
    assert Path(settings.MEDIA_ROOT) not in path.parents
    assert private_pdf.profile_pdf.url.startswith('/private-media/')


def test_anonymous_cannot_open_private_file(client, private_pdf):
    assert client.get(private_pdf.profile_pdf.url).status_code == 404


def test_wrong_role_cannot_open_private_file(client, private_pdf):
    client.force_login(make_staff('clan_admin'))
    assert client.get(private_pdf.profile_pdf.url).status_code == 404


@pytest.mark.parametrize('role', ['genealogy_admin', 'content_admin'])
def test_allowed_role_can_open_private_file(client, private_pdf, role):
    client.force_login(make_staff(role))
    r = client.get(private_pdf.profile_pdf.url)
    assert r.status_code == 200
    assert b''.join(r.streaming_content) == PDF
    assert r['Cache-Control'] == 'private, no-store'


def test_gate_rejects_unknown_and_traversal_paths(client, superadmin):
    client.force_login(superadmin)
    for name in ['persons/pdfs/nope.pdf', '../settings.py', 'persons/pdfs/../../manage.py', 'random/file.txt']:
        assert client.get('/private-media/' + name).status_code == 404


def test_interview_recording_public_only_when_published(client, world):
    iv = world['interview_draft']
    iv.audio_file = SimpleUploadedFile('raw.mp3', b'ID3\x04' + b'\x00' * 32)
    iv.save()
    url = iv.audio_file.url
    assert client.get(url).status_code == 404
    iv.is_published = True
    iv.save()
    assert client.get(url).status_code == 200


# ── S3 configuration ─────────────────────────────────────────────────────────

def _check(**env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith('AWS_') and k != 'MEDIA_PUBLIC_BASE_URL'}
    env.update({'DEBUG': 'False', 'SECRET_KEY': secrets.token_urlsafe(50), 'ALLOWED_HOSTS': 'x.org',
                'AWS_ACCESS_KEY_ID': 'k', 'AWS_SECRET_ACCESS_KEY': 's',
                'AWS_S3_ENDPOINT_URL': 'https://acct.r2.cloudflarestorage.com', **env_extra})
    probe = ("from django.core.files.storage import storages;"
             "print(type(storages['default']).__name__, type(storages['private']).__name__);"
             "print(storages['private'].url('persons/pdfs/a.pdf'))")
    return subprocess.run([sys.executable, 'manage.py', 'shell', '-c', probe], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_s3_storage_selected_by_env_and_private_urls_are_gated():
    r = _check(AWS_STORAGE_BUCKET_NAME='phf-media', AWS_PRIVATE_STORAGE_BUCKET_NAME='phf-private',
               MEDIA_PUBLIC_BASE_URL='https://media.example.org')
    assert r.returncode == 0, r.stderr
    assert 'S3Storage PrivateS3Storage' in r.stdout
    assert '/private-media/persons/pdfs/a.pdf' in r.stdout


def test_public_bucket_cannot_double_as_private_bucket():
    r = _check(AWS_STORAGE_BUCKET_NAME='phf-media', MEDIA_PUBLIC_BASE_URL='https://media.example.org')
    assert r.returncode != 0 and 'AWS_PRIVATE_STORAGE_BUCKET_NAME' in r.stderr
