"""YouTube / Vimeo video links.

Editors may paste any common YouTube or Vimeo URL (watch, share, shorts,
embed). Only those hosts are accepted, and pages always build the iframe
`src` from the extracted video ID, never from the raw URL, so nothing else
can ever be framed.
"""
import re
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import ValidationError

YOUTUBE_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
VIMEO_ID = re.compile(r'^\d{1,12}$')
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
                 'youtube-nocookie.com', 'www.youtube-nocookie.com'}
VIMEO_HOSTS = {'vimeo.com', 'www.vimeo.com', 'player.vimeo.com'}

EMBED_FRAME_HOSTS = ['https://www.youtube-nocookie.com', 'https://player.vimeo.com']


def parse_video_url(url):
    """Return ('youtube'|'vimeo', id) or None."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https'):
        return None
    host = (parts.hostname or '').lower()
    segments = [s for s in parts.path.split('/') if s]

    if host in YOUTUBE_HOSTS:
        vid = None
        if segments[:1] == ['watch']:
            vid = parse_qs(parts.query).get('v', [None])[0]
        elif len(segments) >= 2 and segments[0] in ('embed', 'shorts', 'live', 'v'):
            vid = segments[1]
        if vid and YOUTUBE_ID.match(vid):
            return 'youtube', vid
        return None
    if host in ('youtu.be', 'www.youtu.be'):
        if segments and YOUTUBE_ID.match(segments[0]):
            return 'youtube', segments[0]
        return None
    if host in VIMEO_HOSTS:
        if host == 'player.vimeo.com':
            segments = segments[1:] if segments[:1] == ['video'] else []
        candidates = [s for s in segments if VIMEO_ID.match(s)]
        if candidates:
            return 'vimeo', candidates[0]
    return None


def embed_url(url):
    parsed = parse_video_url(url)
    if not parsed:
        return ''
    kind, vid = parsed
    if kind == 'youtube':
        return f'https://www.youtube-nocookie.com/embed/{vid}'
    return f'https://player.vimeo.com/video/{vid}'


def validate_video_url(value):
    if value and not parse_video_url(value):
        raise ValidationError(
            'Enter a YouTube or Vimeo link (e.g. https://www.youtube.com/watch?v=…, '
            'https://youtu.be/…, or https://vimeo.com/123456).', code='invalid_video_url')
