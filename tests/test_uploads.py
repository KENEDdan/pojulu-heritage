"""Phase 3: upload validation and image sanitising."""
import io
import re

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.core import validators as v
from apps.genealogy.models import Person

GPS_IFD = 0x8825
EXE = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff' + b'\x00' * 200
PHP = b'<?php system($_GET["c"]); ?>'


def jpeg_bytes(size=(2400, 1200), gps=True, orientation=None, color=(200, 30, 30)):
    img = Image.new('RGB', size, color)
    exif = Image.Exif()
    exif[0x010F] = 'PhoneMaker'  # Make
    if gps:
        exif[GPS_IFD] = {1: 'N', 2: (4.0, 51.0, 0.0), 3: 'E', 4: (31.0, 36.0, 0.0)}
    if orientation:
        exif[0x0112] = orientation
    out = io.BytesIO()
    img.save(out, 'JPEG', exif=exif)
    return out.getvalue()


def png_bytes(size=(50, 40), alpha=False):
    img = Image.new('RGBA' if alpha else 'RGB', size, (0, 128, 0, 100) if alpha else (0, 128, 0))
    out = io.BytesIO()
    img.save(out, 'PNG')
    return out.getvalue()


def upload(name, content):
    return SimpleUploadedFile(name, content)


# ── validators ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('validator,name,content', [
    (v.validate_image, 'holiday.jpg', EXE),                 # renamed .exe
    (v.validate_image, 'shell.png', PHP),                   # renamed .php
    (v.validate_image, 'shell.php', PHP),                   # wrong extension outright
    (v.validate_image, 'virus.exe', EXE),
    (v.validate_pdf, 'cv.pdf', PHP),
    (v.validate_pdf, 'cv.pdf', EXE),
    (v.validate_audio, 'song.mp3', EXE),
    (v.validate_video, 'clip.mp4', PHP),
    (v.validate_media, 'photo.jpg', EXE),
    (v.validate_media, 'doc.docx', b'PK\x03\x04garbage'),
    (v.validate_media, 'page.html', b'<script>alert(1)</script>'),
    (v.validate_media, 'image.svg', b'<svg onload="alert(1)"/>'),
])
def test_rejects_disguised_or_disallowed_files(validator, name, content):
    with pytest.raises(ValidationError):
        validator(upload(name, content))


def test_rejects_corrupt_image():
    good = jpeg_bytes(gps=False)
    with pytest.raises(ValidationError):
        v.validate_image(upload('broken.jpg', good[:len(good) // 3]))


def test_rejects_oversized_files(monkeypatch):
    big = upload('huge.jpg', b'\xff\xd8' + b'\x00' * (v.IMAGE_MAX + 1))
    with pytest.raises(ValidationError, match='too large'):
        v.validate_image(big)
    with pytest.raises(ValidationError, match='too large'):
        v.validate_pdf(upload('huge.pdf', b'%PDF-' + b'0' * v.PDF_MAX))


@pytest.mark.parametrize('validator,name,content', [
    (v.validate_image, 'a.jpg', jpeg_bytes(size=(20, 20))),
    (v.validate_image, 'a.PNG', png_bytes()),
    (v.validate_pdf, 'a.pdf', b'%PDF-1.7\n%...'),
    (v.validate_audio, 'a.mp3', b'ID3\x04\x00' + b'\x00' * 20),
    (v.validate_audio, 'a.wav', b'RIFF\x24\x00\x00\x00WAVEfmt '),
    (v.validate_audio, 'a.ogg', b'OggS\x00\x02' + b'\x00' * 20),
    (v.validate_audio, 'a.m4a', b'\x00\x00\x00\x20ftypM4A ' + b'\x00' * 8),
    (v.validate_video, 'a.mp4', b'\x00\x00\x00\x20ftypisom' + b'\x00' * 8),
    (v.validate_video, 'a.webm', b'\x1a\x45\xdf\xa3' + b'\x00' * 20),
    (v.validate_video, 'a.mov', b'\x00\x00\x00\x14ftypqt  ' + b'\x00' * 8),
    (v.validate_media, 'a.pdf', b'%PDF-1.4'),
])
def test_accepts_valid_files(validator, name, content):
    validator(upload(name, content))


def test_accepts_macro_free_docx_and_rejects_macro_docx():
    import zipfile

    def docx(extra=()):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('[Content_Types].xml', '<Types/>')
            z.writestr('word/document.xml', '<w:document/>')
            for n in extra:
                z.writestr(n, 'x')
        return buf.getvalue()
    v.validate_document(upload('a.docx', docx()))
    with pytest.raises(ValidationError, match='macros'):
        v.validate_document(upload('a.docx', docx(['word/vbaProject.bin'])))


# ── model-level processing ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_saved_photo_is_sanitised_and_renamed(world):
    raw = jpeg_bytes(size=(3200, 1600), gps=True)
    assert GPS_IFD in Image.open(io.BytesIO(raw)).getexif()

    p = world['person']
    p.photo = upload('Juma Ladu home address.JPG', raw)
    p.full_clean()
    p.save()

    name = p.photo.name
    assert re.fullmatch(r'persons/photos/\d{4}/\d{2}/[0-9a-f]{32}\.jpg', name), name
    assert 'Juma' not in name
    with p.photo.open('rb') as f:
        img = Image.open(io.BytesIO(f.read()))
        assert img.format == 'JPEG'
        assert max(img.size) == 1600
        exif = img.getexif()
        assert GPS_IFD not in exif and 0x010F not in exif
        assert 'exif' not in img.info


@pytest.mark.django_db
def test_exif_orientation_is_applied_before_stripping(world):
    p = world['person']
    p.photo = upload('rotated.jpg', jpeg_bytes(size=(400, 200), gps=False, orientation=6))  # 90° CW
    p.save()
    with p.photo.open('rb') as f:
        img = Image.open(io.BytesIO(f.read()))
    assert img.size == (200, 400)


@pytest.mark.django_db
def test_transparent_png_becomes_webp_and_opaque_png_becomes_jpeg(world):
    from apps.genealogy.models import PersonMedia
    a = PersonMedia(person=world['person'], file=upload('logo.png', png_bytes(alpha=True)))
    a.full_clean(); a.save()
    b = PersonMedia(person=world['person'], file=upload('flat.png', png_bytes()))
    b.full_clean(); b.save()
    assert a.file.name.endswith('.webp')
    assert b.file.name.endswith('.jpg')


@pytest.mark.django_db
def test_non_image_media_keeps_bytes_but_gets_random_name(world):
    from apps.genealogy.models import PersonMedia
    content = b'%PDF-1.4\nhello'
    m = PersonMedia(person=world['person'], file=upload('Juma passport scan.pdf', content))
    m.full_clean(); m.save()
    assert re.fullmatch(r'persons/media/\d{4}/\d{2}/[0-9a-f]{32}\.pdf', m.file.name)
    with m.file.open('rb') as f:
        assert f.read() == content


# ── end to end through the dashboard ─────────────────────────────────────────

def _mgmt(prefix, total=0):
    return {f'{prefix}-TOTAL_FORMS': str(total), f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000'}


def test_dashboard_rejects_disguised_photo(client, superadmin, world):
    client.force_login(superadmin)
    data = {'first_name': 'New', 'last_name': 'Person', 'gender': 'M',
            'photo': upload('selfie.jpg', EXE), **_mgmt('media_files')}
    r = client.post(reverse('dashboard:person_add'), data)
    assert r.status_code == 200
    assert not Person.objects.filter(first_name='New').exists()
    assert b'not a valid image' in r.content or b'Upload a valid image' in r.content


def test_dashboard_media_formset_rejects_php(client, superadmin, world):
    client.force_login(superadmin)
    data = {'first_name': 'New', 'last_name': 'Person', 'gender': 'M', **_mgmt('media_files', 1),
            'media_files-0-media_type': 'document', 'media_files-0-title': 'x',
            'media_files-0-file': upload('report.pdf', PHP)}
    r = client.post(reverse('dashboard:person_add'), data)
    assert r.status_code == 200
    assert not Person.objects.filter(first_name='New').exists()
    assert b'not a valid PDF' in r.content


def test_dashboard_photo_upload_is_stripped(client, superadmin, world):
    client.force_login(superadmin)
    data = {'first_name': 'Gps', 'last_name': 'Test', 'gender': 'F',
            'photo': upload('IMG_0001.jpg', jpeg_bytes(gps=True)), **_mgmt('media_files')}
    r = client.post(reverse('dashboard:person_add'), data)
    assert r.status_code == 302, r.content.decode()[:3000]
    p = Person.objects.get(first_name='Gps')
    with p.photo.open('rb') as f:
        assert GPS_IFD not in Image.open(io.BytesIO(f.read())).getexif()
