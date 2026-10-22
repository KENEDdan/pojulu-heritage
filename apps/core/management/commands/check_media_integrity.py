"""Report database records whose files are missing from storage.

    py manage.py check_media_integrity            # report only
    py manage.py check_media_integrity --fail     # exit 1 if anything is missing (for cron/CI)

Checks every FileField/ImageField on the project's models, including rows
in the Trash. Works against local disk or the S3 bucket (one HEAD request
per file), so on a large archive run it off-peak.
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from apps.core.signals import PROJECT_APPS


def file_fields():
    for model in apps.get_models():
        if model._meta.app_label not in PROJECT_APPS or model.__name__.startswith('Historical'):
            continue
        for field in model._meta.get_fields():
            if isinstance(field, models.FileField):
                yield model, field


class Command(BaseCommand):
    help = 'List database records whose stored files are missing.'

    def add_arguments(self, parser):
        parser.add_argument('--fail', action='store_true', help='Exit with status 1 if any file is missing.')

    def handle(self, *args, fail=False, **options):
        checked = missing = 0
        for model, field in file_fields():
            manager = getattr(model, 'all_objects', model._base_manager)
            rows = (manager.exclude(**{field.attname: ''}).exclude(**{f'{field.attname}__isnull': True})
                    .values_list('pk', field.attname).order_by('pk'))
            storage = field.storage
            for pk, name in rows.iterator():
                checked += 1
                try:
                    exists = storage.exists(name)
                except Exception as exc:  # storage unreachable: report, don't crash
                    self.stderr.write(f'ERROR    {model._meta.label}.{field.name} pk={pk}: {name} ({exc})')
                    missing += 1
                    continue
                if not exists:
                    missing += 1
                    self.stdout.write(f'MISSING  {model._meta.label}.{field.name} pk={pk}: {name}')
        summary = f'Checked {checked} file reference(s); {missing} missing.'
        if missing:
            self.stdout.write(self.style.WARNING(summary))
            if fail:
                raise CommandError(summary)
        else:
            self.stdout.write(self.style.SUCCESS(summary))
