"""Family (will) accounts: access is limited to the owner and, once revealed,
to immediate relatives who know the passphrase."""
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.genealogy.models import Person
from apps.wills.models import FamilyAccount, Will
from tests.conftest import PASSWORD

PASSPHRASE = 'river-stone-mango-tree'


def account_for(person, username, must_change=False):
    user = User.objects.create_user(username, password=PASSWORD)
    return FamilyAccount.objects.create(user=user, person=person, must_change_password=must_change)


@pytest.fixture
def family(world):
    father, child = world['father'], world['person']            # child.father = father
    stranger = Person.objects.create(first_name='Un', last_name='Related', is_verified=True)
    acc_father = account_for(father, 'father')
    acc_child = account_for(child, 'child')
    acc_stranger = account_for(stranger, 'stranger')
    will = Will.objects.create(account=acc_father)
    will.set_content('I leave the cattle to my son.', PASSPHRASE)
    will.save()
    return {'father': acc_father, 'child': acc_child, 'stranger': acc_stranger, 'will': will}


def test_will_is_encrypted_at_rest(family):
    raw = bytes(Will.objects.get(pk=family['will'].pk).content_encrypted)
    assert b'cattle' not in raw
    assert family['will'].try_decrypt('wrong passphrase') is None
    assert family['will'].try_decrypt(PASSPHRASE) == 'I leave the cattle to my son.'


def test_unrevealed_will_is_not_visible_to_relatives(client, family):
    client.force_login(family['child'].user)
    assert client.get(reverse('wills:will_view', args=[family['will'].pk])).status_code == 404


def test_revealed_will_visible_to_relative_with_passphrase(client, family):
    family['will'].is_revealed = True
    family['will'].save()
    client.force_login(family['child'].user)
    url = reverse('wills:will_view', args=[family['will'].pk])
    assert client.get(url).status_code == 200
    r = client.post(url, {'passphrase': PASSPHRASE})
    assert 'I leave the cattle to my son.' in r.content.decode()
    r = client.post(url, {'passphrase': 'guess'})
    assert 'cattle' not in r.content.decode()


def test_revealed_will_not_visible_to_non_relative(client, family):
    family['will'].is_revealed = True
    family['will'].save()
    client.force_login(family['stranger'].user)
    r = client.post(reverse('wills:will_view', args=[family['will'].pk]), {'passphrase': PASSPHRASE})
    assert r.status_code == 403
    assert 'cattle' not in r.content.decode()


def test_staff_and_anonymous_cannot_use_family_pages(client, family, staff_factory):
    url = reverse('wills:dashboard')
    assert client.get(url).status_code == 302
    client.force_login(staff_factory('content_admin'))
    assert client.get(url).status_code == 403


def test_deactivated_family_account_is_logged_out(client, family):
    acc = family['child']
    client.force_login(acc.user)
    assert client.get(reverse('wills:dashboard')).status_code == 200
    acc.is_active = False
    acc.save()
    r = client.get(reverse('wills:dashboard'))
    assert r.status_code == 302 and r.url == reverse('wills:login')
    assert '_auth_user_id' not in client.session


def test_first_login_forces_password_change(client, world):
    acc = account_for(world['father'], 'newbie', must_change=True)
    client.post(reverse('wills:login'), {'username': 'newbie', 'password': PASSWORD})
    r = client.get(reverse('wills:dashboard'))
    assert r.status_code == 302 and r.url == reverse('wills:change_password')
    # The new password must satisfy the 12-character policy.
    r = client.post(reverse('wills:change_password'), {'new_password': 'short', 'confirm_password': 'short'})
    assert r.status_code == 200
    acc.refresh_from_db()
    assert acc.must_change_password


def test_superadmin_reveal_is_post_and_cannot_decrypt(client, superadmin, family):
    client.force_login(superadmin)
    url = reverse('dashboard:will_reveal', args=[family['will'].pk])
    page = client.get(url).content.decode()
    assert 'cattle' not in page
    client.post(url)
    family['will'].refresh_from_db()
    assert family['will'].is_revealed and family['will'].revealed_by == superadmin


def test_will_content_is_not_in_history_tables(family):
    from django.apps import apps
    assert not any(m.__name__ == 'HistoricalWill' for m in apps.get_models())
