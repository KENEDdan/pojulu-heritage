"""Phase 6: soft delete, Trash, audit trail, genealogy integrity."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.clans.models import Clan
from apps.dashboard.forms import ClanForm, PersonForm
from apps.genealogy.models import Person
from apps.memorial.models import MemorialRecord
from tests.conftest import make_staff


def _mgmt(prefix, total=0):
    return {f'{prefix}-TOTAL_FORMS': str(total), f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000'}


# ── soft delete & Trash ──────────────────────────────────────────────────────

SOFT = [('person_delete', 'person', Person), ('clan_delete', 'clan', Clan)]


@pytest.mark.parametrize('view,key,model', SOFT)
def test_dashboard_delete_is_soft(client, superadmin, world, view, key, model):
    obj = world[key]
    url = obj.get_absolute_url()
    assert client.get(url).status_code == 200
    client.force_login(superadmin)
    r = client.post(reverse(f'dashboard:{view}', args=[obj.pk]))
    assert r.status_code == 302
    assert not model.objects.filter(pk=obj.pk).exists()
    gone = model.all_objects.get(pk=obj.pk)
    assert gone.is_deleted and gone.deleted_by == superadmin and gone.deleted_at
    client.logout()
    assert client.get(url).status_code == 404


def test_soft_deleted_person_hidden_from_relations_and_search(client, superadmin, world):
    world['person'].soft_delete(superadmin)
    for url in [world['father'].get_absolute_url(), world['clan'].get_absolute_url(),
                world['family'].get_absolute_url(), reverse('core:search') + '?q=Juma',
                reverse('genealogy:tree', args=[world['father'].slug]), '/sitemap.xml']:
        assert 'Juma Ladu' not in client.get(url).content.decode() and '/juma-ladu/' not in client.get(url).content.decode(), url


def test_memorial_of_soft_deleted_person_is_hidden(client, superadmin, world):
    world['father'].soft_delete(superadmin)
    assert client.get(world['memorial'].get_absolute_url()).status_code == 404


def test_trash_lists_and_restores(client, superadmin, world):
    client.force_login(superadmin)
    p = world['person']
    client.post(reverse('dashboard:person_delete', args=[p.pk]))
    html = client.get(reverse('dashboard:trash')).content.decode()
    assert 'Juma Ladu' in html
    r = client.post(reverse('dashboard:trash_restore', args=['person', p.pk]))
    assert r.status_code == 302
    p.refresh_from_db()
    assert not p.is_deleted and p.deleted_by is None
    client.logout()
    assert client.get(p.get_absolute_url()).status_code == 200


def test_purge_is_post_only_and_deletes_record(client, superadmin, world):
    p = world['person']
    client.force_login(superadmin)
    client.post(reverse('dashboard:person_delete', args=[p.pk]))
    assert client.get(reverse('dashboard:trash_purge', args=['person', p.pk])).status_code == 405
    assert client.get(reverse('dashboard:trash_restore', args=['person', p.pk])).status_code == 405
    r = client.post(reverse('dashboard:trash_purge', args=['person', p.pk]))
    assert r.status_code == 302
    assert not Person.all_objects.filter(pk=p.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_purge_removes_stored_file_after_commit(client, world):
    from pathlib import Path
    from django.contrib.auth.models import User
    su = User.objects.create_superuser('root2', 'r2@example.org', 'x-Very-long-pass-123')
    p = world['person']
    p.profile_pdf = SimpleUploadedFile('cv.pdf', b'%PDF-1.4 x')
    p.save()
    path = Path(p.profile_pdf.path)
    client.force_login(su)
    client.post(reverse('dashboard:person_delete', args=[p.pk]))
    assert path.exists()  # soft delete keeps files
    client.post(reverse('dashboard:trash_purge', args=['person', p.pk]))
    assert not path.exists()


def test_purge_blocked_for_person_with_will_account(client, superadmin, world):
    from django.contrib.auth.models import User
    from apps.wills.models import FamilyAccount
    p = world['person']
    FamilyAccount.objects.create(user=User.objects.create_user('fam', password='x'), person=p)
    client.force_login(superadmin)
    client.post(reverse('dashboard:person_delete', args=[p.pk]))
    client.post(reverse('dashboard:trash_purge', args=['person', p.pk]))
    assert Person.all_objects.filter(pk=p.pk).exists()


@pytest.mark.parametrize('role', ['clan_admin', 'content_admin', 'genealogy_admin'])
def test_only_superadmin_can_use_trash(client, world, role):
    p = world['person']
    p.soft_delete()
    client.force_login(make_staff(role))
    assert client.get(reverse('dashboard:trash')).status_code in (302, 403)
    client.post(reverse('dashboard:trash_restore', args=['person', p.pk]))
    client.post(reverse('dashboard:trash_purge', args=['person', p.pk]))
    p.refresh_from_db()
    assert p.is_deleted


def test_trash_rejects_unknown_kind_and_live_records(client, superadmin, world):
    client.force_login(superadmin)
    assert client.post(reverse('dashboard:trash_restore', args=['user', 1])).status_code == 404
    assert client.post(reverse('dashboard:trash_purge', args=['person', world['person'].pk])).status_code == 404


def test_editing_child_of_trashed_parent_still_saves(client, superadmin, world):
    world['father'].soft_delete(superadmin)
    child = world['person']
    form = PersonForm(instance=child, data={
        'first_name': 'Juma', 'last_name': 'Ladu', 'gender': 'M', 'father': world['father'].pk,
        'clan': world['clan'].pk, 'family': world['family'].pk, 'is_verified': 'on'})
    assert form.is_valid(), form.errors


def test_clan_name_in_trash_gives_friendly_error(world):
    world['clan'].soft_delete()
    form = ClanForm(data={'name': 'Gumbo', 'payam': 'kupera', 'description': 'again'})
    assert not form.is_valid()
    assert 'in the Trash' in str(form.errors['name'])


def test_memorial_in_trash_gives_friendly_error(world):
    from apps.dashboard.forms import MemorialRecordForm
    world['memorial'].soft_delete()
    form = MemorialRecordForm(data={'person': world['father'].pk, 'tribute': 't'})
    assert not form.is_valid() and 'in the Trash' in str(form.errors)


# ── history ──────────────────────────────────────────────────────────────────

def test_history_records_acting_user(client, world):
    user = make_staff('clan_admin')
    client.force_login(user)
    clan = world['clan']
    client.post(reverse('dashboard:clan_edit', args=[clan.pk]), {
        'name': 'Gumbo', 'payam': 'kupera', 'description': 'Edited by clan admin', **_mgmt('media_files')})
    latest = clan.history.first()
    assert latest.history_user == user and latest.description == 'Edited by clan admin'


def test_soft_delete_is_recorded_in_history_with_user(client, superadmin, world):
    client.force_login(superadmin)
    client.post(reverse('dashboard:person_delete', args=[world['person'].pk]))
    rec = Person.history.filter(id=world['person'].pk).first()
    assert rec.is_deleted and rec.history_user == superadmin


def test_activity_log_page(client, superadmin, world):
    client.force_login(superadmin)
    client.post(reverse('dashboard:person_delete', args=[world['person'].pk]))
    html = client.get(reverse('dashboard:activity_log')).content.decode()
    assert 'Moved to Trash' in html and 'Juma Ladu' in html
    filtered = client.get(reverse('dashboard:activity_log'), {'user': superadmin.pk, 'model': 'person'})
    assert filtered.status_code == 200 and 'Moved to Trash' in filtered.content.decode()
    other = client.get(reverse('dashboard:activity_log'), {'model': 'news'}).content.decode()
    assert 'Moved to Trash' not in other


def test_activity_log_is_superadmin_only(client, world):
    client.force_login(make_staff('content_admin'))
    assert client.get(reverse('dashboard:activity_log')).status_code in (302, 403)


# ── genealogy integrity ──────────────────────────────────────────────────────

def _person_form(instance, **overrides):
    data = {'first_name': instance.first_name, 'last_name': instance.last_name, 'gender': instance.gender,
            'birth_year': instance.birth_year, 'death_year': instance.death_year}
    data.update({k: v for k, v in overrides.items() if v is not None})
    return PersonForm(instance=instance, data=data)


def test_cannot_be_own_parent(world):
    p = world['person']
    p.father_id = p.pk
    with pytest.raises(Exception) as e:
        p.full_clean()
    assert 'own father' in str(e.value)


def test_cycle_is_rejected_with_friendly_error(world):
    grandfather, child = world['father'], world['person']   # child.father = grandfather
    grandchild = Person.objects.create(first_name='Grand', last_name='Child', father=child, gender='F')
    form = _person_form(grandfather, father=grandchild.pk)   # would make grandfather his own grandson's son
    assert not form.is_valid()
    assert 'loop in the family tree' in str(form.errors['father'])
    form = _person_form(grandfather, mother=child.pk)        # parent and child of the same person
    assert not form.is_valid() and 'descendant' in str(form.errors['mother'])


def test_father_and_mother_must_differ(world):
    a = world['father']
    form = _person_form(world['person'], father=a.pk, mother=a.pk)
    assert not form.is_valid() and 'different people' in str(form.errors)


def test_death_before_birth_rejected(world):
    form = _person_form(world['person'], birth_year='1960', death_year='approx. 1950s', is_deceased='on')
    assert not form.is_valid() and 'before year of birth' in str(form.errors['death_year'])
    form = _person_form(world['person'], birth_date='1960-05-01', death_date='1959-01-01')
    assert not form.is_valid()


def test_database_constraints_backstop(world):
    p = world['person']
    with pytest.raises(IntegrityError), transaction.atomic():
        Person.objects.filter(pk=p.pk).update(father=p)
    with pytest.raises(IntegrityError), transaction.atomic():
        Person.objects.filter(pk=p.pk).update(father=world['father'], mother=world['father'])


def test_tree_survives_corrupt_cycle(client, world, django_assert_max_num_queries):
    a, b = world['father'], world['person']                  # b.father = a
    Person.objects.filter(pk=a.pk).update(father=b)          # bypass validation: a <-> b loop
    with django_assert_max_num_queries(60):
        r = client.get(reverse('genealogy:tree', args=[a.slug]) + '?gens=10')
    assert r.status_code == 200
    r = client.get(b.get_absolute_url())
    assert r.status_code == 200
