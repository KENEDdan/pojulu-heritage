from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.conf import settings

from .models import FamilyAccount, Will
from .forms import SetWillForm, UpdateWillForm, PassphrasePromptForm, ChangeLoginPasswordForm


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _login_attempts_key(request, username):
    return f'family_login_attempts:{_client_ip(request)}:{username.lower()}'


def require_family_account(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('wills:login')
        try:
            account = request.user.family_account
        except FamilyAccount.DoesNotExist:
            raise PermissionDenied
        if not account.is_active:
            logout(request)
            return redirect('wills:login')
        if account.must_change_password and view_func.__name__ != 'family_change_password':
            return redirect('wills:change_password')
        request.family_account = account
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def family_login(request):
    if request.user.is_authenticated and hasattr(request.user, 'family_account'):
        return redirect('wills:dashboard')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        key = _login_attempts_key(request, username)
        attempts = cache.get(key, 0)
        if attempts >= settings.LOGIN_ATTEMPT_LIMIT:
            error = 'Too many failed login attempts. Please try again in a few minutes.'
        else:
            user = authenticate(request, username=username, password=password)
            if user and hasattr(user, 'family_account') and user.family_account.is_active:
                cache.delete(key)
                login(request, user)
                return redirect('wills:dashboard')
            cache.set(key, attempts + 1, settings.LOGIN_LOCKOUT_SECONDS)
            error = 'Invalid username or password.'
    return render(request, 'wills/login.html', {'error': error})


def family_logout(request):
    logout(request)
    return redirect('wills:login')


@require_family_account
def family_change_password(request):
    account = request.family_account
    form = ChangeLoginPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.user.set_password(form.cleaned_data['new_password'])
        request.user.save()
        account.must_change_password = False
        account.save()
        messages.success(request, 'Password updated. Please log in again.')
        logout(request)
        return redirect('wills:login')
    return render(request, 'wills/change_password.html', {'form': form})


@require_family_account
def family_dashboard(request):
    account = request.family_account
    will = Will.objects.filter(account=account).first()
    relative_pks = [r.pk for r in account.immediate_relatives]
    shared_wills = Will.objects.filter(
        is_revealed=True, account__person__pk__in=relative_pks
    ).select_related('account__person')
    return render(request, 'wills/dashboard.html', {
        'account': account,
        'will': will,
        'shared_wills': shared_wills,
    })


@require_family_account
def family_will_write(request):
    """Write or overwrite the will. The passphrase used to encrypt it is
    never stored — it exists only for the duration of this request."""
    account = request.family_account
    will, _ = Will.objects.get_or_create(account=account)
    if will.is_revealed:
        return redirect('wills:will_read')

    is_first_time = not will.content_encrypted
    FormClass = SetWillForm if is_first_time else UpdateWillForm
    form = FormClass(request.POST or None)
    passphrase_error = None

    if request.method == 'POST' and form.is_valid():
        passphrase = form.cleaned_data['passphrase']
        if is_first_time:
            will.set_content(form.cleaned_data['content'], passphrase)
            will.save()
            messages.success(request, 'Your will has been saved. It is encrypted with your passphrase alone — '
                                       'the Foundation cannot read or recover it.')
            messages.warning(request, 'Important: share this passphrase with your family through your own means '
                                       '(in person, a sealed letter, etc.) — never send it through this website. '
                                       'If it is lost, this will can never be recovered by anyone.')
            return redirect('wills:dashboard')
        else:
            if will.try_decrypt(passphrase) is None:
                passphrase_error = 'Incorrect passphrase. Your will was not changed.'
            else:
                will.set_content(form.cleaned_data['content'], passphrase)
                will.save()
                messages.success(request, 'Your will has been updated.')
                return redirect('wills:dashboard')

    return render(request, 'wills/will_write.html', {
        'form': form, 'is_first_time': is_first_time, 'passphrase_error': passphrase_error,
    })


@require_family_account
def family_will_read(request):
    """View your own will read-only — still passphrase-gated, since the
    app never retains a way to decrypt it on your behalf either."""
    account = request.family_account
    will = get_object_or_404(Will, account=account)
    content = None
    form = PassphrasePromptForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        content = will.try_decrypt(form.cleaned_data['passphrase'])
        if content is None:
            form.add_error('passphrase', 'Incorrect passphrase.')
    return render(request, 'wills/will_read.html', {'will': will, 'form': form, 'content': content, 'is_own': True})


@require_family_account
def family_will_view(request, pk):
    account = request.family_account
    will = get_object_or_404(Will, pk=pk, is_revealed=True)
    relative_pks = {r.pk for r in account.immediate_relatives}
    if will.account.person.pk not in relative_pks:
        raise PermissionDenied
    content = None
    form = PassphrasePromptForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        content = will.try_decrypt(form.cleaned_data['passphrase'])
        if content is None:
            form.add_error('passphrase', 'Incorrect passphrase.')
    return render(request, 'wills/will_read.html', {'will': will, 'form': form, 'content': content, 'is_own': False})
