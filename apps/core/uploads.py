"""Safe upload handling: random filenames and in-memory image sanitising.

Everything here works on file *objects*, never on `.path`, so it behaves the
same with local storage and with S3-compatible buckets.
"""
import io
import uuid

from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible

from .validators import IMAGE_EXTENSIONS, MAX_IMAGE_PIXELS, extension_of

DEFAULT_MAX_EDGE = 1600
JPEG_QUALITY = 85


@deconstructible
class UploadTo:
    """upload_to callable: `<prefix>/<yyyy>/<mm>/<uuid>.<ext>`.

    The user's filename is discarded entirely; only its (already validated)
    extension is kept, normalised to lower case.
    """

    def __init__(self, prefix):
        self.prefix = prefix.strip('/')

    def __call__(self, instance, filename):
        ext = extension_of(filename) or 'bin'
        ext = {'jpeg': 'jpg'}.get(ext, ext)
        return f'{self.prefix}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}'

    def __eq__(self, other):
        return isinstance(other, UploadTo) and other.prefix == self.prefix


def process_image(fileobj, max_edge=DEFAULT_MAX_EDGE, quality=JPEG_QUALITY):
    """Auto-orient, strip all metadata (EXIF incl. GPS, XMP, comments),
    shrink to `max_edge` on the long side and re-encode.

    Returns (bytes, extension). Opaque images become JPEG; images with real
    transparency become WebP. Animated GIFs keep only their first frame.
    """
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    fileobj.seek(0)
    with Image.open(fileobj) as src:
        src.load()
        icc = src.info.get('icc_profile')
        img = ImageOps.exif_transpose(src)

    has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
    if has_alpha:
        img = img.convert('RGBA')
        if img.getchannel('A').getextrema()[0] == 255:
            has_alpha = False
    if not has_alpha:
        img = img.convert('RGB')

    img.thumbnail((max_edge, max_edge), Image.LANCZOS)

    out = io.BytesIO()
    # A fresh save without exif=/xmp= drops all metadata; the ICC colour
    # profile is kept because it carries no personal data.
    extra = {'icc_profile': icc} if icc else {}
    if has_alpha:
        img.save(out, 'WEBP', quality=quality, method=4, **extra)
        ext = 'webp'
    else:
        img.save(out, 'JPEG', quality=quality, optimize=True, progressive=True, **extra)
        ext = 'jpg'
    fileobj.seek(0)
    return out.getvalue(), ext


class _SanitisingMixin:
    """Re-encodes newly uploaded images just before they are written to
    storage. Non-image files pass through untouched."""

    def __init__(self, *args, image_max_edge=DEFAULT_MAX_EDGE, **kwargs):
        self.image_max_edge = image_max_edge
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.image_max_edge != DEFAULT_MAX_EDGE:
            kwargs['image_max_edge'] = self.image_max_edge
        return name, path, args, kwargs

    def pre_save(self, model_instance, add):
        f = getattr(model_instance, self.attname)
        if f and not f._committed and extension_of(f.name) in IMAGE_EXTENSIONS:
            data, ext = process_image(f.file, self.image_max_edge)
            f.file = ContentFile(data)
            f.name = f'image.{ext}'
        return super().pre_save(model_instance, add)


class SafeFileField(_SanitisingMixin, models.FileField):
    pass


class SafeImageField(_SanitisingMixin, models.ImageField):
    pass
