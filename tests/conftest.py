import datetime

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache

from apps.dashboard.models import AdminProfile, ROLE_CHOICES

ROLES = [r for r, _ in ROLE_CHOICES]
PASSWORD = 'Correct-Horse-Battery-9'


@pytest.fixture(autouse=True)
def _fast_hashing_and_clean_cache(settings, tmp_path):
    # Argon2 is deliberately slow; tests don't need that.
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    settings.MEDIA_ROOT = tmp_path / 'media'
    settings.PRIVATE_MEDIA_ROOT = tmp_path / 'private'
    cache.clear()
    yield
    cache.clear()


def make_staff(role, username=None, active=True):
    user = User.objects.create_user(
        username=username or role, email=f'{username or role}@example.org',
        password=PASSWORD, first_name=role.title(), is_staff=True,
    )
    profile = AdminProfile.objects.create(user=user, role=role, is_active=active)
    profile.assign_permissions()
    if not active:
        user.is_active = False
        user.save()
    return user


@pytest.fixture
def frozen_ratelimit_window(monkeypatch):
    """django-ratelimit uses fixed windows aligned to the wall clock; pin the
    window so a test's requests can't straddle a minute boundary."""
    import django_ratelimit.core as rl
    monkeypatch.setattr(rl, '_get_window', lambda value, period: 4_000_000_000)


@pytest.fixture
def superadmin(db):
    return User.objects.create_superuser('root', 'root@example.org', PASSWORD)


@pytest.fixture
def staff_factory(db):
    return make_staff


@pytest.fixture
def world(db):
    """One published and one unpublished record of every public model."""
    from apps.clans.models import Clan, ClanChief, ClanEvent
    from apps.genealogy.models import Family, Person
    from apps.memorial.models import MemorialRecord
    from apps.achievements.models import Achievement
    from apps.marriages.models import Marriage
    from apps.cultural.models import CulturalRecord
    from apps.elders.models import ElderInterview
    from apps.news.models import NewsPost
    from apps.submissions.models import Submission

    w = {}
    w['clan'] = Clan.objects.create(name='Gumbo', payam='kupera', description='Public clan', is_verified=True)
    w['clan_draft'] = Clan.objects.create(name='Hidden', payam='kupera', description='Draft clan')
    w['chief'] = ClanChief.objects.create(clan=w['clan'], name='Lado', title='Chief')
    w['event'] = ClanEvent.objects.create(clan=w['clan'], title='Founding', description='d', year='1900')
    w['family'] = Family.objects.create(name='Ladu Family', clan=w['clan'], is_verified=True)
    w['family_draft'] = Family.objects.create(name='Secret Family', clan=w['clan'])
    w['father'] = Person.objects.create(first_name='Elder', last_name='Ladu', clan=w['clan'], family=w['family'],
                                        gender='M', is_verified=True, is_deceased=True, birth_year='1920', death_year='1990')
    w['person'] = Person.objects.create(
        first_name='Juma', last_name='Ladu', clan=w['clan'], family=w['family'], father=w['father'],
        gender='M', is_verified=True, phone='+211 900 000 111', email_contact='juma@example.org',
        address='Plot 7, Hidden Street', birth_year='1960',
    )
    w['person_draft'] = Person.objects.create(first_name='Draft', last_name='Person', clan=w['clan'],
                                              father=w['father'], gender='F')
    w['memorial'] = MemorialRecord.objects.create(person=w['father'], tribute='Remembered')
    w['memorial_draft'] = MemorialRecord.objects.create(person=w['person_draft'], tribute='Not public')
    w['achievement'] = Achievement.objects.create(person_name='Juma', category='education', title='Degree',
                                                  description='d', is_verified=True)
    w['achievement_draft'] = Achievement.objects.create(person_name='X', category='other', title='Secret award',
                                                        description='d')
    w['marriage'] = Marriage.objects.create(husband=w['father'], wife_name='Mary', year='1955', is_verified=True)
    w['marriage_draft'] = Marriage.objects.create(husband_name='Hidden', wife_name='Draft', year='1999')
    w['cultural'] = CulturalRecord.objects.create(title='Harvest song', record_type='song', content='la la',
                                                  is_verified=True)
    w['cultural_draft'] = CulturalRecord.objects.create(title='Draft song', record_type='song', content='x')
    w['interview'] = ElderInterview.objects.create(elder_name='Elder Ladu', interviewer='Ken', summary='s',
                                                   is_published=True, interview_date=datetime.date(2024, 1, 2))
    w['interview_draft'] = ElderInterview.objects.create(elder_name='Draft Elder', interviewer='Ken', summary='s')
    w['news'] = NewsPost.objects.create(title='Launch', excerpt='e', content='c', is_published=True)
    w['news_draft'] = NewsPost.objects.create(title='Draft news', excerpt='e', content='c')
    w['submission'] = Submission.objects.create(submission_type='person', submitter_name='S', submitter_email='s@x.org',
                                                submitter_relationship='son', content='c', subject_name='Subj')
    return w
