"""TOTP two-factor authentication for superadmins (see docs/HARDENING.md, Phase 9).

The password step lives in views.dashboard_login. When a superuser has a
confirmed authenticator, that view does not log them in; it records a short-
lived "2FA pending" marker in the session and sends them here.
"""
import base64
import io
import logging
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django_otp import user_has_device
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

security_log = logging.getLogger('phf.security')

PENDING_KEY = '2fa_pending'
PENDING_SECONDS = 300
MAX_CODE_ATTEMPTS = 5
RECOVERY_CODE_COUNT = 10


# ── policy ───────────────────────────────────────────────────────────────────

def superadmin_2fa_ok(user):
    """May this (authenticated) user use superadmin powers in this session?"""
    if not getattr(user, 'is_superuser', False):
        return True
    if user_has_device(user):
        # is_verified() is installed by OTPMiddleware; anything else is unverified.
        return bool(getattr(user, 'is_verified', lambda: False)())
    return not settings.REQUIRE_SUPERADMIN_2FA


def superadmin_2fa_redirect(request):
    """Where a superuser must go before using superadmin pages, or None."""
    user = request.user
    if not user.is_superuser or superadmin_2fa_ok(user):
        return None
    if user_has_device(user):
        # Session predates 2FA enrolment (e.g. enrolled elsewhere): sign in again.
        from django.contrib.auth import logout
        logout(request)
        messages.info(request, 'Please sign in again with your authenticator code.')
        return redirect('dashboard:login')
    messages.warning(request, 'Two-factor authentication is required for Super Administrators. '
                              'Set up your authenticator app to continue.')
    return redirect('dashboard:twofactor')


# ── login, step 2 ────────────────────────────────────────────────────────────

def begin_pending_login(request, user):
    request.session.cycle_key()
    request.session[PENDING_KEY] = {'uid': user.pk, 'backend': user.backend, 'ts': time.time(), 'tries': 0}
    return redirect('dashboard:login_verify')


def _pending_user(request):
    pending = request.session.get(PENDING_KEY)
    if not pending or time.time() - pending['ts'] > PENDING_SECONDS:
        request.session.pop(PENDING_KEY, None)
        return None, None
    user = get_user_model().objects.filter(pk=pending['uid'], is_active=True, is_superuser=True).first()
    return user, pending


def _verify(user, token):
    token = (token or '').strip().replace(' ', '').replace('-', '')
    if not token:
        return None
    if token.isdigit() and len(token) == 6:
        devices = TOTPDevice.objects.filter(user=user, confirmed=True)
    else:
        devices = StaticDevice.objects.filter(user=user, confirmed=True)
        token = token.lower()
    for device in devices:
        allowed, _ = device.verify_is_allowed()
        if allowed and device.verify_token(token):
            return device
    return None


def login_verify(request):
    user, pending = _pending_user(request)
    if user is None:
        messages.error(request, 'Your sign-in session expired. Please enter your password again.')
        return redirect('dashboard:login')
    error = None
    if request.method == 'POST':
        device = _verify(user, request.POST.get('token'))
        if device is not None:
            request.session.pop(PENDING_KEY, None)
            user.backend = pending['backend']
            user.otp_device = device          # persisted by django_otp's user_logged_in handler
            login(request, user)
            security_log.info('Dashboard login (2FA via %s): user=%s', type(device).__name__, user.username)
            if isinstance(device, StaticDevice):
                left = device.token_set.count()
                messages.warning(request, f'You signed in with a recovery code. {left} recovery code(s) left.')
            return redirect('dashboard:home')
        pending['tries'] += 1
        request.session[PENDING_KEY] = pending
        security_log.warning('Failed 2FA code: user=%s attempt=%s', user.username, pending['tries'])
        if pending['tries'] >= MAX_CODE_ATTEMPTS:
            request.session.pop(PENDING_KEY, None)
            messages.error(request, 'Too many incorrect codes. Please sign in again.')
            return redirect('dashboard:login')
        error = 'That code is not valid. Check your authenticator app and try again.'
    return render(request, 'dashboard/login_verify.html', {'error': error})


# ── enrolment & management ───────────────────────────────────────────────────

def _superuser_only(view):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('dashboard:login')
        if not request.user.is_superuser:
            return redirect('dashboard:home')
        return view(request, *args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper


def _qr_data_uri(url):
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return 'data:image/svg+xml;base64,' + base64.b64encode(buf.getvalue()).decode()


def _new_recovery_codes(user):
    device, _ = StaticDevice.objects.get_or_create(user=user, name='Recovery codes', defaults={'confirmed': True})
    device.token_set.all().delete()
    codes = [StaticToken.random_token() for _ in range(RECOVERY_CODE_COUNT)]
    StaticToken.objects.bulk_create([StaticToken(device=device, token=c) for c in codes])
    return codes


@_superuser_only
def twofactor(request):
    user = request.user
    confirmed = TOTPDevice.objects.filter(user=user, confirmed=True).first()
    if confirmed:
        if not user.is_verified():
            return superadmin_2fa_redirect(request) or redirect('dashboard:login')
        return render(request, 'dashboard/twofactor.html', {
            'enabled': True,
            'recovery_left': StaticToken.objects.filter(device__user=user).count(),
            'required': settings.REQUIRE_SUPERADMIN_2FA,
            'page_title': 'Two-Factor Authentication',
        })

    device = TOTPDevice.objects.filter(user=user, confirmed=False).first() or \
        TOTPDevice.objects.create(user=user, name='Authenticator app', confirmed=False)
    error = None
    if request.method == 'POST':
        token = (request.POST.get('token') or '').strip().replace(' ', '')
        if token.isdigit() and device.verify_token(token):
            device.confirmed = True
            device.save()
            user.otp_device = device
            from django_otp import login as otp_login
            otp_login(request, device)
            codes = _new_recovery_codes(user)
            security_log.warning('2FA enabled: user=%s', user.username)
            return render(request, 'dashboard/recovery_codes.html', {'codes': codes, 'page_title': 'Recovery Codes'})
        error = 'That code did not match. Make sure your phone\'s clock is correct and try the newest code.'
    secret = base64.b32encode(device.bin_key).decode().rstrip('=')
    return render(request, 'dashboard/twofactor.html', {
        'enabled': False, 'qr': _qr_data_uri(device.config_url),
        'secret': ' '.join(secret[i:i + 4] for i in range(0, len(secret), 4)),
        'error': error, 'required': settings.REQUIRE_SUPERADMIN_2FA,
        'page_title': 'Set Up Two-Factor Authentication',
    })


@_superuser_only
@require_POST
def regenerate_recovery_codes(request):
    if not (user_has_device(request.user) and request.user.is_verified()):
        return redirect('dashboard:twofactor')
    codes = _new_recovery_codes(request.user)
    security_log.warning('2FA recovery codes regenerated: user=%s', request.user.username)
    return render(request, 'dashboard/recovery_codes.html', {'codes': codes, 'page_title': 'Recovery Codes'})


@_superuser_only
@require_POST
def disable_twofactor(request):
    user = request.user
    if settings.REQUIRE_SUPERADMIN_2FA:
        messages.error(request, 'Two-factor authentication is required for Super Administrators and cannot be turned off.')
        return redirect('dashboard:twofactor')
    if not user.is_verified() or _verify(user, request.POST.get('token')) is None:
        messages.error(request, 'Enter a current authenticator code to turn off two-factor authentication.')
        return redirect('dashboard:twofactor')
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()
    security_log.warning('2FA disabled: user=%s', user.username)
    messages.success(request, 'Two-factor authentication has been turned off.')
    return redirect(reverse('dashboard:twofactor'))
