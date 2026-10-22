"""Remove a superadmin's authenticator and recovery codes (lost phone and
no recovery codes left). They can sign in with just their password and
must enrol again if REQUIRE_SUPERADMIN_2FA is on.

    py manage.py reset_2fa <username>
"""
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice


class Command(BaseCommand):
    help = "Remove a user's two-factor devices and recovery codes."

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, username, **options):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f'No user named {username!r}.')
        n_totp, _ = TOTPDevice.objects.filter(user=user).delete()
        n_static, _ = StaticDevice.objects.filter(user=user).delete()
        logging.getLogger('phf.security').warning('2FA reset from the command line: user=%s', username)
        self.stdout.write(self.style.SUCCESS(f'Removed two-factor devices for {username} '
                                             f'({n_totp} authenticator, {n_static} recovery records).'))
