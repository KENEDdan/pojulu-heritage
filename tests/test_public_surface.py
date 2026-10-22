"""Phase 5: public surface — submissions removed, rate limits, CSP, video
embeds, robots/sitemap, error pages, social meta."""
import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse
from PIL import Image

from apps.core.embeds import embed_url, parse_video_url


# ── submissions ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('url', ['/submit/', '/submit/success/'])
def test_public_submission_urls_are_gone(client, url):
    assert client.get(url).status_code == 404
    assert client.post(url, {'content': 'spam'}).status_code == 404


# ── search ───────────────────────────────────────────────────────────────────

def test_search_requires_two_characters(client, world):
    html = client.get(reverse('core:search'), {'q': 'J'}).content.decode()
    assert 'at least 2 characters' in html
    assert 'Juma Ladu' not in html


def test_search_query_length_is_capped(client, world):
    r = client.get(reverse('core:search'), {'q': 'Juma' + 'x' * 500})
    assert r.status_code == 200
    assert r.context['query'] == ('Juma' + 'x' * 500)[:100]


def test_search_is_rate_limited_per_ip(client, world):
    url = reverse('core:search')
    for _ in range(30):
        assert client.get(url, {'q': 'Juma'}).status_code == 200
    r = client.get(url, {'q': 'Juma'})
    assert r.status_code == 429
    assert b'Please slow down' in r.content
    # A different client IP is unaffected.
    assert client.get(url, {'q': 'Juma'}, REMOTE_ADDR='203.0.113.9').status_code == 200


def test_tree_is_rate_limited(client, world):
    url = reverse('genealogy:tree', args=[world['person'].slug])
    codes = [client.get(url).status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429


# ── CSP ──────────────────────────────────────────────────────────────────────

def test_csp_report_only_header(client, world):
    r = client.get(reverse('core:home'))
    policy = r['Content-Security-Policy-Report-Only']
    assert "default-src 'self'" in policy
    assert 'https://cdn.jsdelivr.net' in policy and 'https://fonts.googleapis.com' in policy
    assert 'https://fonts.gstatic.com' in policy
    assert 'frame-src https://www.youtube-nocookie.com https://player.vimeo.com' in policy
    assert "object-src 'none'" in policy and "frame-ancestors 'none'" in policy
    assert 'Content-Security-Policy' not in r  # not enforcing yet


def test_security_headers_on_public_pages(client, world):
    r = client.get(reverse('core:home'))
    assert r['X-Frame-Options'] == 'DENY'
    assert r['X-Content-Type-Options'] == 'nosniff'
    assert r['Referrer-Policy'] == 'same-origin'


# ── video embeds ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize('url,expected', [
    ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'),
    ('https://youtu.be/dQw4w9WgXcQ?t=5', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'),
    ('https://www.youtube.com/embed/dQw4w9WgXcQ', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'),
    ('https://youtube.com/shorts/dQw4w9WgXcQ', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'),
    ('https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=share', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'),
    ('https://vimeo.com/76979871', 'https://player.vimeo.com/video/76979871'),
    ('https://player.vimeo.com/video/76979871?h=abc', 'https://player.vimeo.com/video/76979871'),
])
def test_video_urls_convert_to_embeds(url, expected):
    assert embed_url(url) == expected


@pytest.mark.parametrize('url', [
    'https://evil.example.com/embed/dQw4w9WgXcQ',
    'https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ',
    'javascript:alert(1)//youtube.com/watch?v=dQw4w9WgXcQ',
    'https://www.youtube.com/watch?v=<script>',
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ"onload="x',
    'https://vimeo.com/channels/staffpicks',
    'ftp://youtube.com/watch?v=dQw4w9WgXcQ',
])
def test_hostile_video_urls_rejected(url):
    assert parse_video_url(url) is None
    assert embed_url(url) == ''


def test_model_rejects_non_video_host(world):
    rec = world['cultural']
    rec.video_url = 'https://evil.example.com/player'
    with pytest.raises(ValidationError):
        rec.full_clean()


def test_template_embeds_only_safe_url(client, world):
    rec = world['cultural']
    rec.video_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    rec.save()
    html = client.get(rec.get_absolute_url()).content.decode()
    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in html
    # A bad URL that predates validation is simply not embedded.
    type(rec).objects.filter(pk=rec.pk).update(video_url='https://evil.example.com/x')
    html = client.get(rec.get_absolute_url()).content.decode()
    assert 'evil.example.com' not in html and '<iframe' not in html


# ── robots / sitemap ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_robots_txt(client):
    r = client.get('/robots.txt')
    body = r.content.decode()
    assert r['Content-Type'].startswith('text/plain')
    for line in ['Disallow: /dashboard/', 'Disallow: /admin/', 'Disallow: /private-media/', 'Disallow: /family/']:
        assert line in body
    assert 'Sitemap: http://testserver/sitemap.xml' in body


def test_sitemap_lists_only_public_records(client, world):
    p = world['father']
    world['person'].is_private = True
    world['person'].save()
    body = client.get('/sitemap.xml').content.decode()
    for key in ['clan', 'family', 'father', 'news', 'interview']:
        assert world[key].get_absolute_url() in body, key
    for key in ['clan_draft', 'family_draft', 'person_draft', 'person', 'news_draft', 'interview_draft']:
        assert world[key].get_absolute_url() not in body, key


# ── error pages ──────────────────────────────────────────────────────────────

def test_404_uses_phf_design_without_db_queries(client, db, django_assert_num_queries):
    with django_assert_num_queries(0):
        r = client.get('/no-such-page/')
    assert r.status_code == 404
    assert b'Pojulu Heritage Foundation' in r.content and b'/static/css/errors.css' in r.content


@pytest.mark.parametrize('template', ['400.html', '403.html', '403_csrf.html', '404.html', '429.html', '500.html'])
def test_error_templates_render_without_context_or_db(template, django_assert_num_queries, db):
    with django_assert_num_queries(0):
        html = render_to_string(template)  # 500 is rendered with an empty Context
    assert 'Pojulu Heritage Foundation' in html and '{%' not in html


# ── social meta ──────────────────────────────────────────────────────────────

def _png():
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (0, 90, 0)).save(buf, 'JPEG')
    return SimpleUploadedFile('c.jpg', buf.getvalue())


def test_news_social_meta(client, world):
    post = world['news']
    post.cover_image = _png()
    post.excerpt = 'A <b>big</b> day'
    post.save()
    html = client.get(post.get_absolute_url()).content.decode()
    assert '<meta property="og:title" content="Launch">' in html
    assert '<meta property="og:type" content="article">' in html
    assert '<meta property="og:description" content="A big day">' in html
    assert '<meta property="og:image" content="http://testserver/media/news/covers/' in html
    assert 'summary_large_image' in html


def test_person_meta_never_contains_contact_details(client, world):
    p = world['person']
    p.show_contact_publicly = True
    p.biography = 'Phone me on +211 900 000 111'  # even if staff put it in the bio
    p.save()
    html = client.get(p.get_absolute_url()).content.decode()
    head = html.split('</head>')[0]
    assert '<meta property="og:title" content="Juma Ladu">' in head
    for secret in ['+211 900 000 111', 'juma@example.org', 'Hidden Street']:
        assert secret not in head
