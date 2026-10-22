"""Delete stored files when the row that owns them is permanently deleted.

Soft delete (the Trash) never removes files; this only fires on a real
DELETE, i.e. "Delete permanently" or a cascade from it. Deletion waits until
the transaction commits, so a rolled-back delete never loses a file.
"""
import logging

from django.apps import apps
from django.db import models, transaction
from django.db.models.signals import post_delete

log = logging.getLogger('phf.security')
PROJECT_APPS = {'clans', 'genealogy', 'memorial', 'achievements', 'marriages', 'cultural',
                'elders', 'submissions', 'news'}


def _delete_files(sender, instance, **kwargs):
    for field in sender._meta.get_fields():
        if not isinstance(field, models.FileField):
            continue
        f = getattr(instance, field.attname, None)
        if not f or not f.name:
            continue
        name, storage = f.name, f.storage

        def remove(name=name, storage=storage):
            try:
                storage.delete(name)
            except Exception:  # never let file cleanup break a delete
                log.exception('Could not delete stored file %s', name)
        transaction.on_commit(remove)


def connect_file_cleanup():
    for model in apps.get_models():
        if model._meta.app_label not in PROJECT_APPS or model.__name__.startswith('Historical'):
            continue
        if any(isinstance(f, models.FileField) for f in model._meta.get_fields()):
            post_delete.connect(_delete_files, sender=model, weak=False,
                                dispatch_uid=f'phf-file-cleanup-{model._meta.label}')
