"""Every dashboard page renders for the superadmin, with data and with empty
tables. Catches NoReverseMatch / template errors on pages nobody opened."""
import pytest
from django.urls import reverse

# url name -> key into the `world` fixture for the pk (None = no args)
PAGES = {
    'home': None, 'clan_dashboard': None, 'genealogy_dashboard': None, 'memorial_dashboard': None,
    'cultural_dashboard': None, 'elder_dashboard': None, 'achievement_dashboard': None,
    'content_dashboard': None, 'news_dashboard': None,
    'clan_add': None, 'chief_add': None, 'event_add': None, 'person_add': None, 'family_add': None,
    'marriage_add': None, 'memorial_add': None, 'achievement_add': None, 'cultural_add': None,
    'elder_add': None, 'news_add': None,
    'clan_edit': 'clan', 'chief_edit': 'chief', 'event_edit': 'event', 'person_edit': 'person',
    'family_edit': 'family', 'marriage_edit': 'marriage', 'memorial_edit': 'memorial',
    'achievement_edit': 'achievement', 'cultural_edit': 'cultural', 'elder_edit': 'interview',
    'news_edit': 'news',
    'submission_list': None, 'submission_review': 'submission',
    'accounts': None, 'create_account': None,
    'family_account_list': None, 'family_account_search': None, 'family_account_create_new_person': None,
}
EMPTY_OK = [name for name, key in PAGES.items() if key is None]


@pytest.mark.parametrize('name', sorted(PAGES))
def test_page_renders_with_data(client, superadmin, world, name):
    client.force_login(superadmin)
    key = PAGES[name]
    url = reverse(f'dashboard:{name}', args=[world[key].pk] if key else [])
    r = client.get(url)
    assert r.status_code == 200, (url, r.status_code)


@pytest.mark.parametrize('name', sorted(EMPTY_OK))
def test_page_renders_empty(client, superadmin, name):
    client.force_login(superadmin)
    r = client.get(reverse(f'dashboard:{name}'))
    assert r.status_code == 200


def test_edit_form_includes_media_management_form_inside_main_form(client, superadmin, world):
    """Regression: the media formset used to be rendered inside the delete
    modal's <form>, so edits to clans/persons silently failed to save."""
    client.force_login(superadmin)
    html = client.get(reverse('dashboard:clan_edit', args=[world['clan'].pk])).content.decode()
    main_form = html.split('<form method="post" enctype="multipart/form-data"', 1)[1].split('</form>', 1)[0]
    assert 'media_files-TOTAL_FORMS' in main_form


def _mgmt(prefix, total=0, initial=0):
    return {f'{prefix}-TOTAL_FORMS': str(total), f'{prefix}-INITIAL_FORMS': str(initial),
            f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000'}


def test_clan_edit_saves(client, superadmin, world):
    client.force_login(superadmin)
    clan = world['clan']
    data = {'name': 'Gumbo Renamed', 'payam': clan.payam, 'description': 'x', 'is_verified': 'on',
            **_mgmt('media_files')}
    r = client.post(reverse('dashboard:clan_edit', args=[clan.pk]), data)
    assert r.status_code == 302
    clan.refresh_from_db()
    assert clan.name == 'Gumbo Renamed'


def test_news_add_sets_author(client, superadmin, db):
    from apps.news.models import NewsPost
    client.force_login(superadmin)
    data = {'title': 'Hello', 'post_type': 'news', 'excerpt': 'e', 'content': 'c', 'is_published': 'on',
            **_mgmt('media')}
    r = client.post(reverse('dashboard:news_add'), data)
    assert r.status_code == 302, r.content[:2000]
    post = NewsPost.objects.get(title='Hello')
    assert post.author == superadmin and post.published_at is not None
