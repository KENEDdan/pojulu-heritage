"""Phase 9: TOTP two-factor authentication for superadmins."""
import io
import re
import time

import pytest
from django.core.management import call_command
from django.urls import reverse
from django_otp.oath import TOTP
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from tests.conftest import PASSWORD

LOGIN = 'dashboard:login'


def code(device, offset=0):
    t = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    t.time = time.time() + offset
    return f'{t.token():06d}'


@pytest.fixture
def enrolled(superadmin):
    device = TOTPDevice.objects.create(user=superadmin, name='phone', confirmed=True)
    static = StaticDevice.objects.create(user=superadmin, name='Recovery codes', confirmed=True)
    StaticToken.objects.create(device=static, token='abcd1234efgh5678')
    return device


def password_step(client):
    return client.post(reverse(LOGIN), {'username': 'root', 'password': PASSWORD})


def test_password_alone_does_not_log_in_enrolled_superadmin(client, enrolled):
    r = password_step(client)
    assert r.status_code == 302 and r.url == reverse('dashboard:login_verify')
    assert '_auth_user_id' not in client.session
    assert client.get(reverse('dashboard:home')).status_code == 302  # still anonymous


def test_valid_totp_completes_login(client, enrolled):
    password_step(client)
    r = client.post(reverse('dashboard:login_verify'), {'token': code(enrolled)})
    assert r.status_code == 302 and r.url == reverse('dashboard:home')
    assert client.get(reverse('dashboard:home')).status_code == 200


def test_wrong_code_rejected_and_attempts_capped(client, enrolled):
    password_step(client)
    for _ in range(4):
        r = client.post(reverse('dashboard:login_verify'), {'token': '000000'})
        assert r.status_code == 200 and b'not valid' in r.content
    r = client.post(reverse('dashboard:login_verify'), {'token': '000000'})
    assert r.status_code == 302 and r.url == reverse(LOGIN)
    # The pending state is gone: even a correct code needs the password again.
    r = client.post(reverse('dashboard:login_verify'), {'token': code(enrolled)})
    assert r.url == reverse(LOGIN) and '_auth_user_id' not in client.session


def test_totp_code_cannot_be_replayed(client, enrolled):
    c = code(enrolled)
    password_step(client)
    client.post(reverse('dashboard:login_verify'), {'token': c})
    client.post(reverse('dashboard:logout'))
    password_step(client)
    r = client.post(reverse('dashboard:login_verify'), {'token': c})
    assert r.status_code == 200 and '_auth_user_id' not in client.session


def test_recovery_code_works_once(client, enrolled):
    password_step(client)
    r = client.post(reverse('dashboard:login_verify'), {'token': 'ABCD-1234-EFGH-5678'})
    assert r.status_code == 302 and '_auth_user_id' in client.session
    client.post(reverse('dashboard:logout'))
    password_step(client)
    r = client.post(reverse('dashboard:login_verify'), {'token': 'abcd1234efgh5678'})
    assert r.status_code == 200 and '_auth_user_id' not in client.session


def test_pending_login_expires(client, enrolled, monkeypatch):
    password_step(client)
    real = time.time
    monkeypatch.setattr('apps.dashboard.twofactor.time.time', lambda: real() + 3600)
    r = client.post(reverse('dashboard:login_verify'), {'token': code(enrolled)})
    assert r.url == reverse(LOGIN) and '_auth_user_id' not in client.session


def test_unverified_session_of_enrolled_superadmin_is_rejected(client, superadmin, enrolled):
    client.force_login(superadmin)   # e.g. a session that predates enrolment
    r = client.get(reverse('dashboard:accounts'))
    assert r.status_code == 302 and r.url == reverse(LOGIN)


def test_staff_roles_are_unaffected(client, staff_factory):
    staff_factory('clan_admin')
    r = client.post(reverse(LOGIN), {'username': 'clan_admin', 'password': PASSWORD})
    assert r.url == reverse('dashboard:clan_dashboard')


def test_require_flag_forces_enrolment(client, superadmin, settings):
    settings.REQUIRE_SUPERADMIN_2FA = True
    client.force_login(superadmin)
    r = client.get(reverse('dashboard:accounts'))
    assert r.status_code == 302 and r.url == reverse('dashboard:twofactor')
    r = client.get(reverse('dashboard:clan_dashboard'))
    assert r.url == reverse('dashboard:twofactor')
    assert client.get(reverse('dashboard:twofactor')).status_code == 200


def test_private_media_needs_verified_superadmin_when_enrolled(client, superadmin, enrolled, world):
    from django.core.files.uploadedfile import SimpleUploadedFile
    p = world['person']
    p.profile_pdf = SimpleUploadedFile('a.pdf', b'%PDF-1.4 x')
    p.save()
    client.force_login(superadmin)                 # unverified session
    assert client.get(p.profile_pdf.url).status_code == 404
    client.logout()
    password_step(client)
    client.post(reverse('dashboard:login_verify'), {'token': code(enrolled)})
    assert client.get(p.profile_pdf.url).status_code == 200


def test_enrolment_flow(client, superadmin):
    client.force_login(superadmin)
    html = client.get(reverse('dashboard:twofactor')).content.decode()
    assert 'data:image/svg+xml;base64,' in html
    device = TOTPDevice.objects.get(user=superadmin, confirmed=False)
    assert client.post(reverse('dashboard:twofactor'), {'token': '000000'}).status_code == 200
    device.refresh_from_db()
    assert not device.confirmed
    device.throttle_reset()   # django-otp backs off after a wrong code; skip the wait
    r = client.post(reverse('dashboard:twofactor'), {'token': code(device)})
    device.refresh_from_db()
    assert device.confirmed
    codes = re.findall(r'<div>([a-z0-9]{8,})</div>', r.content.decode())
    assert len(codes) == 10
    # The enrolling session is verified, so superadmin pages keep working.
    assert client.get(reverse('dashboard:accounts')).status_code == 200
    # And the next sign-in needs the second step.
    client.post(reverse('dashboard:logout'))
    assert password_step(client).url == reverse('dashboard:login_verify')


def test_disable_requires_code_and_is_blocked_when_required(client, enrolled, settings):
    password_step(client)
    client.post(reverse('dashboard:login_verify'), {'token': code(enrolled)})
    client.post(reverse('dashboard:twofactor_disable'), {'token': '000000'})
    assert TOTPDevice.objects.filter(pk=enrolled.pk).exists()
    settings.REQUIRE_SUPERADMIN_2FA = True
    client.post(reverse('dashboard:twofactor_disable'), {'token': 'abcd1234efgh5678'})
    assert TOTPDevice.objects.filter(pk=enrolled.pk).exists()
    settings.REQUIRE_SUPERADMIN_2FA = False
    client.post(reverse('dashboard:twofactor_disable'), {'token': 'abcd1234efgh5678'})
    assert not TOTPDevice.objects.filter(user=enrolled.user).exists()


def test_reset_2fa_command(enrolled):
    out = io.StringIO()
    call_command('reset_2fa', 'root', stdout=out)
    assert not TOTPDevice.objects.filter(user=enrolled.user).exists()
    assert not StaticDevice.objects.filter(user=enrolled.user).exists()


@pytest.mark.parametrize('role', ['clan_admin', 'content_admin'])
def test_twofactor_pages_are_superadmin_only(client, staff_factory, role):
    client.force_login(staff_factory(role))
    assert client.get(reverse('dashboard:twofactor')).status_code == 302
    assert not TOTPDevice.objects.exists()
