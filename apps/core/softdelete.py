"""Soft delete.

`objects` (the default manager — also used by related managers and form
dropdowns) hides rows in the Trash; `all_objects` sees everything. Deleting
from the dashboard moves a record to the Trash; only a superadmin can
restore it or delete it permanently.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


def soft_delete_managers(queryset_class):
    """Return (objects, all_objects) managers built on `queryset_class`."""

    class AliveManager(models.Manager.from_queryset(queryset_class)):
        def get_queryset(self):
            return super().get_queryset().filter(is_deleted=False)

    class AllManager(models.Manager.from_queryset(queryset_class)):
        pass

    return AliveManager(), AllManager()


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False, db_index=True, editable=False)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False,
                                   on_delete=models.SET_NULL, related_name='+')

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user if user is not None and user.is_authenticated else None
        self.save()

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()
