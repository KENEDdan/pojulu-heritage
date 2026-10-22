"""Who may open which private file.

Each private file field is listed with the staff roles that may always open
it and, optionally, a rule under which the public may open it (e.g. an elder
interview recording once the interview is published). Superadmins may open
everything. Anyone else gets a 404, so the gate never confirms that a file exists.
"""
import mimetypes
from dataclasses import dataclass
from typing import Callable, Optional

from django.apps import apps
from django.http import FileResponse, Http404, HttpResponseRedirect

GENEALOGY_ROLES = {'genealogy_admin', 'memorial_admin', 'content_admin'}
ELDER_ROLES = {'elder_admin', 'cultural_admin', 'content_admin'}


@dataclass(frozen=True)
class PrivateField:
    model: str                 # "app_label.ModelName"
    field: str
    staff_roles: frozenset
    public_if: Optional[Callable] = None

    def model_class(self):
        return apps.get_model(self.model)

    def prefix(self):
        return self.model_class()._meta.get_field(self.field).upload_to.prefix + '/'


def _interview_published(obj):
    return obj.is_published and not getattr(obj, 'is_deleted', False)


PRIVATE_FIELDS = [
    PrivateField('genealogy.Person', 'profile_pdf', frozenset(GENEALOGY_ROLES)),
    PrivateField('genealogy.PersonEducation', 'certificate', frozenset(GENEALOGY_ROLES)),
    PrivateField('genealogy.PersonMedia', 'file', frozenset(GENEALOGY_ROLES)),
    PrivateField('elders.ElderInterview', 'audio_file', frozenset(ELDER_ROLES), _interview_published),
    PrivateField('elders.ElderInterview', 'video_file', frozenset(ELDER_ROLES), _interview_published),
    PrivateField('submissions.Submission', 'attachment', frozenset({'content_admin'})),
]


def staff_role(user):
    """'superadmin', the active staff role, or None."""
    if not user.is_authenticated or not user.is_active:
        return None
    if user.is_superuser:
        from apps.dashboard.twofactor import superadmin_2fa_ok
        return 'superadmin' if superadmin_2fa_ok(user) else None
    profile = getattr(user, 'admin_profile', None)
    if profile is not None and profile.is_active:
        return profile.role
    return None


def resolve(name):
    """Return (PrivateField, owning object) for a stored file name, or raise 404."""
    if not name or '..' in name.split('/') or name.startswith('/'):
        raise Http404
    for pf in PRIVATE_FIELDS:
        if name.startswith(pf.prefix()):
            manager = getattr(pf.model_class(), 'all_objects', pf.model_class()._default_manager)
            obj = manager.filter(**{pf.field: name}).first()
            if obj is not None:
                return pf, obj
    raise Http404


def can_open(user, pf, obj):
    role = staff_role(user)
    if role == 'superadmin' or role in pf.staff_roles:
        return True
    return bool(pf.public_if and pf.public_if(obj))


def serve(request, name):
    pf, obj = resolve(name)
    if not can_open(request.user, pf, obj):
        raise Http404
    fieldfile = getattr(obj, pf.field)
    storage = fieldfile.storage
    signed = storage.signed_url(name) if hasattr(storage, 'signed_url') else None
    if signed:
        response = HttpResponseRedirect(signed)
    else:
        if not storage.exists(name):
            raise Http404
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        response = FileResponse(storage.open(name, 'rb'), content_type=content_type)
        response['Content-Disposition'] = 'inline'
    # Never let a shared cache keep a copy of a private file or its signed URL.
    response['Cache-Control'] = 'private, no-store'
    return response
