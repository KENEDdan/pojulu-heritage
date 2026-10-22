import logging

from django.contrib.auth import logout
from django.shortcuts import redirect

security_log = logging.getLogger('phf.security')


class ActiveAccountMiddleware:
    """Ends the session of a staff or family account the moment it is
    deactivated — not just at their next login. Superusers have no profile and
    rely on User.is_active (which Django's auth backend already enforces)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not user.is_superuser:
            blocked, login_url = self._blocked(user)
            if blocked:
                security_log.warning('Deactivated account session ended: user=%s path=%s', user.username, request.path)
                logout(request)
                return redirect(login_url)
        return self.get_response(request)

    @staticmethod
    def _blocked(user):
        from apps.dashboard.models import AdminProfile
        from apps.wills.models import FamilyAccount
        try:
            if not user.admin_profile.is_active:
                return True, 'dashboard:login'
        except AdminProfile.DoesNotExist:
            pass
        try:
            if not user.family_account.is_active:
                return True, 'wills:login'
        except FamilyAccount.DoesNotExist:
            pass
        return False, None
