import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.clans.models import Clan
from apps.genealogy.models import HistoricalPerson, Person
from apps.news.models import NewsPost

pytestmark = pytest.mark.django_db


def test_demo_data_refuses_without_debug(settings):
    settings.DEBUG = False
    for args in ([], ['--extend']):
        with pytest.raises(CommandError, match='DEBUG=True'):
            call_command('demo_data', *args)
    assert not Person.all_objects.exists()
    assert not User.objects.exists()


def test_demo_data_seeds_and_deletes_only_its_own_rows(settings):
    settings.DEBUG = True
    real_admin = User.objects.create_superuser('realadmin', 'r@example.org', 'x' * 16)
    real_clan = Clan.objects.create(name='Real Clan', payam='kupera', description='Real', is_verified=True)

    call_command('demo_data')
    assert Person.all_objects.count() == 88
    assert NewsPost.all_objects.filter(is_deleted=True).exists()
    media = settings.MEDIA_ROOT
    assert any(p.suffix == '.jpg' for p in media.rglob('*'))
    with pytest.raises(CommandError):
        call_command('demo_data')  # refuses to seed twice

    call_command('demo_data', '--delete')
    assert Person.all_objects.count() == 0
    assert HistoricalPerson.objects.count() == 0
    assert list(Clan.all_objects.all()) == [real_clan]
    assert list(User.objects.all()) == [real_admin]
    assert not any(p.is_file() for p in media.rglob('*'))
    assert not any(p.is_file() for p in settings.PRIVATE_MEDIA_ROOT.rglob('*')) if settings.PRIVATE_MEDIA_ROOT.exists() else True
