"""Media storage backends.

Two storage aliases are configured in settings.STORAGES:

* ``default``  — public media (photos/covers meant for the public site).
* ``private``  — sensitive media (profile PDFs, certificates, personal media,
  elder-interview recordings, submission attachments).

Both are local FileSystemStorage when no bucket is configured, and
S3-compatible (Cloudflare R2 / Backblaze B2) otherwise. Private files never
have a directly reachable URL: ``.url`` always points at the authenticated
``core:private_media`` view, which checks permissions and then streams the
file (local) or redirects to a short-lived signed URL (S3).
"""
import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages
from django.urls import reverse
from django.utils.functional import cached_property


def get_private_storage():
    """Callable used as `storage=` on private fields, so migrations record the
    callable rather than an environment-specific storage instance."""
    return storages['private']


class _GatedUrlMixin:
    def url(self, name):
        return reverse('core:private_media', kwargs={'name': name})


class PrivateFileSystemStorage(_GatedUrlMixin, FileSystemStorage):
    """Local private storage under PRIVATE_MEDIA_ROOT — outside MEDIA_ROOT, so
    the DEBUG /media/ static handler can never serve it."""

    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @cached_property
    def base_url(self):
        return '/private-media/'

    def signed_url(self, name, expire=None):
        return None  # local files are streamed by the gate view


try:
    from storages.backends.s3 import S3Storage
except ImportError:  # pragma: no cover - django-storages is in requirements
    S3Storage = None


if S3Storage is not None:
    class PrivateS3Storage(_GatedUrlMixin, S3Storage):
        def signed_url(self, name, expire=None):
            return S3Storage.url(self, name, expire=expire or settings.PRIVATE_MEDIA_URL_EXPIRE)
