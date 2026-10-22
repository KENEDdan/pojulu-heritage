"""Phase 2: authentication, lockout, role isolation, deactivation."""
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.urls import get_resolver, reverse

from apps.dashboard.forms import CreateAdminForm
from tests.conftest import PASSWORD, ROLES, make_staff

# url name -> roles (besides superadmin) allowed in, and the `world` key for pk
ACCESS = {
    'clan_dashboard':        ({'clan_admin', 'content_admin'}, None),
    'clan_add':              ({'clan_admin', 'content_admin'}, None),
    'clan_edit':             ({'clan_admin', 'content_admin'}, 'clan'),
    'chief_add':             ({'clan_admin', 'content_admin'}, None),
    'chief_edit':            ({'clan_admin', 'content_admin'}, 'chief'),
    'event_add':             ({'clan_admin', 'content_admin'}, None),
    'event_edit':            ({'clan_admin', 'content_admin'}, 'event'),
    'genealogy_dashboard':   ({'genealogy_admin', 'content_admin'}, None),
    'person_add':            ({'genealogy_admin', 'memorial_admin', 'content_admin'}, None),
    'person_edit':           ({'genealogy_admin', 'memorial_admin', 'content_admin'}, 'person'),
    'family_add':            ({'genealogy_admin', 'content_admin'}, None),
    'family_edit':           ({'genealogy_admin', 'content_admin'}, 'family'),
    'marriage_add':          ({'genealogy_admin', 'content_admin'}, None),
    'marriage_edit':         ({'genealogy_admin', 'content_admin'}, 'marriage'),
    'memorial_dashboard':    ({'memorial_admin', 'content_admin'}, None),
    'memorial_add':          ({'memorial_admin', 'content_admin'}, None),
    'memorial_edit':         ({'memorial_admin', 'content_admin'}, 'memorial'),
    'achievement_dashboard': ({'achievement_admin', 'content_admin'}, None),
    'achievement_add':       ({'achievement_admin', 'content_admin'}, None),
    'achievement_edit':      ({'achievement_admin', 'content_admin'}, 'achievement'),
    'cultural_dashboard':    ({'cultural_admin', 'content_admin'}, None),
    'cultural_add':          ({'cultural_admin', 'content_admin'}, None),
    'cultural_edit':         ({'cultural_admin', 'content_admin'}, 'cultural'),
    'elder_dashboard':       ({'elder_admin', 'cultural_admin', 'content_admin'}, None),
    'elder_add':             ({'elder_admin', 'cultural_admin', 'content_admin'}, None),
    'elder_edit':            ({'elder_admin', 'cultural_admin', 'content_admin'}, 'interview'),
    'news_dashboard':        ({'content_admin'}, None),
    'news_add':              ({'content_admin'}, None),
    'news_edit':             ({'content_admin'}, 'news'),
    'content_dashboard':     ({'content_admin'}, None),
    'submission_list':       ({'content_admin'}, None),
    'submission_review':     ({'content_admin'}, 'submission'),
    'home':                  (set(), None),
    'accounts':              (set(), None),
    'create_account':        (set(), None),
    'family_account_list':   (set(), None),
    'family_account_search': (set(), None),
    'trash':                 (set(), None),
    'activity_log':          (set(), None),
}

DELETES = {
    'clan_delete': 'clan', 'chief_delete': 'chief', 'event_delete': 'event', 'person_delete': 'person',
    'family_delete': 'family', 'memorial_delete': 'memorial', 'achievement_delete': 'achievement',
    'marriage_delete': 'marriage', 'cultural_delete': 'cultural', 'elder_delete': 'interview',
    'news_delete': 'news',
}


def _dashboard_routes():
    resolver = get_resolver()
    for p in resolver.url_patterns:
        if getattr(p, 'namespace', None) == 'dashboard':
            for sub in p.url_patterns:
                yield sub


def _fill(route_pattern):
    return (str(route_pattern).replace('<int:pk>', '1').replace('<int:person_id>', '1')
            .replace('<slug:kind>', 'person'))


@pytest.mark.django_db
@pytest.mark.parametrize('method', ['get', 'post'])
def test_anonymous_is_redirected_from_every_dashboard_url(client, method):
    login_url = reverse('dashboard:login')
    checked = 0
    for p in _dashboard_routes():
        if p.name in ('login', 'logout'):
            continue
        url = '/dashboard/' + _fill(p.pattern)
        r = getattr(client, method)(url)
        assert r.status_code == 302 and r.url.startswith(login_url), (url, r.status_code)
        checked += 1
    assert checked > 50


@pytest.mark.parametrize('role', ROLES)
def test_role_access_matrix(client, world, role):
    user = make_staff(role)
    client.force_login(user)
    for name, (allowed, key) in ACCESS.items():
        url = reverse(f'dashboard:{name}', args=[world[key].pk] if key else [])
        r = client.get(url)
        if role in allowed:
            assert r.status_code == 200, (role, name, r.status_code)
        else:
            assert r.status_code in (302, 403), (role, name, r.status_code)
            if r.status_code == 302:
                assert r.url != url


@pytest.mark.parametrize('role', ROLES)
def test_only_superadmin_can_delete(client, world, role):
    client.force_login(make_staff(role))
    for name, key in DELETES.items():
        obj = world[key]
        client.post(reverse(f'dashboard:{name}', args=[obj.pk]))
        assert type(obj).objects.filter(pk=obj.pk).exists(), (role, name)


def test_delete_endpoints_are_post_only(client, superadmin, world):
    client.force_login(superadmin)
    for name, key in DELETES.items():
        obj = world[key]
        r = client.get(reverse(f'dashboard:{name}', args=[obj.pk]))
        assert r.status_code == 405, name
        assert type(obj).objects.filter(pk=obj.pk).exists()


@pytest.mark.parametrize('role', ROLES)
def test_only_superadmin_manages_accounts(client, staff_factory, role):
    target = staff_factory('elder_admin', username='target')
    client.force_login(staff_factory(role, username=f'actor_{role}'))
    client.post(reverse('dashboard:deactivate_account', args=[target.admin_profile.pk]))
    client.post(reverse('dashboard:create_account'), {
        'first_name': 'E', 'last_name': 'Vil', 'email': 'evil@example.org', 'username': 'evil',
        'password': 'Another-Strong-Pass-77', 'role': 'content_admin'})
    target.admin_profile.refresh_from_db()
    assert target.admin_profile.is_active
    assert not User.objects.filter(username='evil').exists()


def test_deactivated_staff_session_is_ended_on_next_request(client, staff_factory):
    user = staff_factory('clan_admin')
    client.force_login(user)
    assert client.get(reverse('dashboard:clan_dashboard')).status_code == 200
    user.admin_profile.is_active = False
    user.admin_profile.save()
    r = client.get(reverse('clans:list'))  # any page, not only the dashboard
    assert r.status_code == 302 and r.url == reverse('dashboard:login')
    assert '_auth_user_id' not in client.session


def test_deactivated_staff_cannot_log_in(client, staff_factory):
    staff_factory('clan_admin', active=False)
    r = client.post(reverse('dashboard:login'), {'username': 'clan_admin', 'password': PASSWORD})
    assert r.status_code == 200
    assert '_auth_user_id' not in client.session


def test_family_account_cannot_reach_dashboard(client, world):
    from apps.wills.models import FamilyAccount
    u = User.objects.create_user('fam', password=PASSWORD)
    FamilyAccount.objects.create(user=u, person=world['person'], must_change_password=False)
    client.force_login(u)
    assert client.get(reverse('dashboard:clan_dashboard')).status_code == 403
    # Previously this bounced between dashboard:home and the login page forever.
    r = client.get(reverse('dashboard:login'))
    assert r.status_code == 200
    assert client.get(reverse('dashboard:home')).status_code == 403


def test_successful_login_redirects_to_role_dashboard(client, staff_factory):
    staff_factory('cultural_admin')
    r = client.post(reverse('dashboard:login'), {'username': 'cultural_admin', 'password': PASSWORD})
    assert r.status_code == 302 and r.url == reverse('dashboard:cultural_dashboard')


def test_lockout_after_five_failures(client, staff_factory):
    staff_factory('clan_admin')
    url = reverse('dashboard:login')
    for _ in range(5):
        r = client.post(url, {'username': 'clan_admin', 'password': 'wrong-password'})
    # Now even the correct password is refused.
    r = client.post(url, {'username': 'clan_admin', 'password': PASSWORD})
    assert r.status_code == 429
    assert b'temporarily locked' in r.content
    assert '_auth_user_id' not in client.session


def test_lockout_is_per_username_and_ip(client, staff_factory):
    staff_factory('clan_admin')
    staff_factory('elder_admin')
    url = reverse('dashboard:login')
    for _ in range(5):
        client.post(url, {'username': 'clan_admin', 'password': 'wrong'})
    r = client.post(url, {'username': 'elder_admin', 'password': PASSWORD})
    assert r.status_code == 302  # a different username from the same IP is unaffected


def test_family_login_is_also_protected(client, world):
    from apps.wills.models import FamilyAccount
    u = User.objects.create_user('fam', password=PASSWORD)
    FamilyAccount.objects.create(user=u, person=world['person'], must_change_password=False)
    url = reverse('wills:login')
    for _ in range(5):
        client.post(url, {'username': 'fam', 'password': 'nope'})
    assert client.post(url, {'username': 'fam', 'password': PASSWORD}).status_code == 429


def test_spoofed_forwarded_for_does_not_evade_lockout(client, staff_factory, settings):
    settings.TRUSTED_PROXY_COUNT = 1
    staff_factory('clan_admin')
    url = reverse('dashboard:login')
    for i in range(5):
        # Attacker rotates the client-supplied part; the proxy-appended hop is constant.
        client.post(url, {'username': 'clan_admin', 'password': 'x'}, HTTP_X_FORWARDED_FOR=f'10.0.0.{i}, 198.51.100.7')
    r = client.post(url, {'username': 'clan_admin', 'password': PASSWORD}, HTTP_X_FORWARDED_FOR='10.9.9.9, 198.51.100.7')
    assert r.status_code == 429


@pytest.mark.parametrize('url_name', ['dashboard:logout', 'wills:logout'])
def test_logout_is_post_only(client, superadmin, url_name):
    client.force_login(superadmin)
    assert client.get(reverse(url_name)).status_code == 405
    assert '_auth_user_id' in client.session
    client.post(reverse(url_name))
    assert '_auth_user_id' not in client.session


@pytest.mark.django_db
def test_create_admin_form_enforces_password_policy():
    base = {'first_name': 'Ana', 'last_name': 'Lado', 'email': 'ana@example.org', 'username': 'analado',
            'role': 'clan_admin'}
    assert not CreateAdminForm({**base, 'password': 'short1!'}).is_valid()          # < 12 chars
    assert not CreateAdminForm({**base, 'password': '123456789012345'}).is_valid()  # numeric
    assert not CreateAdminForm({**base, 'password': 'analado2024!!'}).is_valid()    # similar to username
    assert CreateAdminForm({**base, 'password': 'Moss-Riverbank-Lantern-41'}).is_valid()


def test_security_settings():
    assert settings.PASSWORD_HASHERS  # tests override to MD5; check the real config below
    from django.conf import settings as live  # noqa
    import importlib
    mod = importlib.import_module('pojulu_heritage.settings')
    assert mod.PASSWORD_HASHERS[0].endswith('Argon2PasswordHasher')
    assert any(h.endswith('PBKDF2PasswordHasher') for h in mod.PASSWORD_HASHERS)
    assert mod.AUTHENTICATION_BACKENDS[0] == 'axes.backends.AxesStandaloneBackend'
    assert mod.SESSION_COOKIE_AGE == 3600 and mod.SESSION_SAVE_EVERY_REQUEST
    assert mod.SESSION_COOKIE_HTTPONLY and mod.SESSION_COOKIE_SAMESITE == 'Lax'
    min_len = [v for v in mod.AUTH_PASSWORD_VALIDATORS if v['NAME'].endswith('MinimumLengthValidator')][0]
    assert min_len['OPTIONS']['min_length'] == 12
