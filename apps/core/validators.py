"""Upload validators.

Each validator checks the *content* of a newly uploaded file (magic bytes /
Pillow decode), not just its extension or the browser-supplied content type.
They are attached to the model fields, so every code path that calls
full_clean() — dashboard forms, inline formsets, the Django admin — is covered.

Files already in storage (FieldFile._committed is True) are skipped: they
were validated when uploaded, and re-reading a 200 MB recording from the
bucket on every unrelated edit would be wasteful.
"""
import os
import zipfile

from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat

MB = 1024 * 1024

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
PDF_EXTENSIONS = ['pdf']
DOCUMENT_EXTENSIONS = ['pdf', 'docx']
AUDIO_EXTENSIONS = ['mp3', 'wav', 'm4a', 'ogg', 'aac']
VIDEO_EXTENSIONS = ['mp4', 'webm', 'mov']

IMAGE_MAX = 8 * MB
PDF_MAX = 25 * MB
AUDIO_MAX = 200 * MB
VIDEO_MAX = 500 * MB

# Pillow's decompression-bomb guard: refuse absurd pixel counts outright.
MAX_IMAGE_PIXELS = 60_000_000


def extension_of(name):
    return os.path.splitext(name or '')[1].lower().lstrip('.')


def _is_new_upload(value):
    return bool(value) and not getattr(value, '_committed', False)


def _check_extension(value, allowed, kind):
    ext = extension_of(value.name)
    if ext not in allowed:
        raise ValidationError(
            f'Unsupported {kind} type ".{ext}". Allowed: {", ".join("." + e for e in allowed)}.',
            code='invalid_extension')
    return ext


def _check_size(value, limit):
    if value.size > limit:
        raise ValidationError(
            f'File too large ({filesizeformat(value.size)}). Maximum is {filesizeformat(limit)}.',
            code='file_too_large')


def _head(value, n=64):
    f = value.file if hasattr(value, 'file') else value
    pos = f.tell() if hasattr(f, 'tell') else 0
    f.seek(0)
    data = f.read(n)
    f.seek(pos)
    return data


def _reject(kind):
    raise ValidationError(f'This file is not a valid {kind}. It may be corrupt or mislabelled.',
                          code='invalid_content')


# ── individual validators ────────────────────────────────────────────────────

def validate_image(value):
    if not _is_new_upload(value):
        return
    _check_extension(value, IMAGE_EXTENSIONS, 'image')
    _check_size(value, IMAGE_MAX)
    from PIL import Image
    f = value.file if hasattr(value, 'file') else value
    try:
        f.seek(0)
        with Image.open(f) as img:
            if img.format not in ('JPEG', 'PNG', 'GIF', 'WEBP'):
                _reject('image')
            w, h = img.size
            if w * h > MAX_IMAGE_PIXELS:
                raise ValidationError('Image dimensions are too large.', code='image_too_large')
            img.verify()
        # verify() barely inspects JPEGs; a full decode catches truncated or
        # corrupt pixel data too (the pixel count was bounded above).
        f.seek(0)
        with Image.open(f) as img:
            img.load()
    except ValidationError:
        raise
    except Exception:
        _reject('image')
    finally:
        f.seek(0)


def validate_pdf(value):
    if not _is_new_upload(value):
        return
    _check_extension(value, PDF_EXTENSIONS, 'document')
    _check_size(value, PDF_MAX)
    if not _head(value, 5) == b'%PDF-':
        _reject('PDF')


def _validate_docx(value):
    _check_size(value, PDF_MAX)
    if _head(value, 4) != b'PK\x03\x04':
        _reject('Word document')
    f = value.file if hasattr(value, 'file') else value
    try:
        f.seek(0)
        with zipfile.ZipFile(f) as z:
            names = set(z.namelist())
    except zipfile.BadZipFile:
        _reject('Word document')
    finally:
        f.seek(0)
    if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
        _reject('Word document')
    if any(n.lower().endswith('vbaproject.bin') for n in names):
        raise ValidationError('Documents containing macros are not accepted.', code='macro')


def validate_document(value):
    """PDF, or a macro-free .docx."""
    if not _is_new_upload(value):
        return
    ext = _check_extension(value, DOCUMENT_EXTENSIONS, 'document')
    if ext == 'pdf':
        validate_pdf(value)
    else:
        _validate_docx(value)


def _audio_ok(ext, head):
    if ext == 'mp3':
        return head[:3] == b'ID3' or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)
    if ext == 'wav':
        return head[:4] == b'RIFF' and head[8:12] == b'WAVE'
    if ext == 'm4a':
        return head[4:8] == b'ftyp'
    if ext == 'ogg':
        return head[:4] == b'OggS'
    if ext == 'aac':
        return head[:3] == b'ID3' or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0)
    return False


def validate_audio(value):
    if not _is_new_upload(value):
        return
    ext = _check_extension(value, AUDIO_EXTENSIONS, 'audio')
    _check_size(value, AUDIO_MAX)
    if not _audio_ok(ext, _head(value, 16)):
        _reject('audio file')


def _video_ok(ext, head):
    if ext == 'mp4':
        return head[4:8] == b'ftyp'
    if ext == 'mov':
        return head[4:8] in (b'ftyp', b'moov', b'mdat', b'wide', b'free', b'skip')
    if ext == 'webm':
        return head[:4] == b'\x1a\x45\xdf\xa3'
    return False


def validate_video(value):
    if not _is_new_upload(value):
        return
    ext = _check_extension(value, VIDEO_EXTENSIONS, 'video')
    _check_size(value, VIDEO_MAX)
    if not _video_ok(ext, _head(value, 16)):
        _reject('video file')


def validate_document_or_image(value):
    if not _is_new_upload(value):
        return
    ext = extension_of(value.name)
    if ext in IMAGE_EXTENSIONS:
        validate_image(value)
    else:
        validate_document(value)


MEDIA_EXTENSIONS = IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS + AUDIO_EXTENSIONS + VIDEO_EXTENSIONS


def validate_media(value):
    """Mixed media (PersonMedia / ClanMedia / NewsMedia / submissions):
    dispatch on extension, then verify the content matches it."""
    if not _is_new_upload(value):
        return
    ext = _check_extension(value, MEDIA_EXTENSIONS, 'file')
    if ext in IMAGE_EXTENSIONS:
        validate_image(value)
    elif ext in DOCUMENT_EXTENSIONS:
        validate_document(value)
    elif ext in AUDIO_EXTENSIONS:
        validate_audio(value)
    else:
        validate_video(value)


# ── Legacy names referenced by existing migrations ───────────────────────────

def validate_upload_size(value):
    """Kept only because migrations 0002/0003 import it. The real limits now
    live in the per-type validators above."""
    return None
