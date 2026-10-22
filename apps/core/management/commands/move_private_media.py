"""Move files that belong in private storage out of public storage.

Fields such as Person.profile_pdf used to live in the public media store.
Run this once after deploying Phase 4 (it is idempotent):

    py manage.py move_private_media --dry-run
    py manage.py move_private_media
"""
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from apps.core.private_media import PRIVATE_FIELDS


class Command(BaseCommand):
    help = 'Move files of private fields from public (default) storage into private storage.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, dry_run=False, **options):
        moved = missing = already = 0
        for pf in PRIVATE_FIELDS:
            model = pf.model_class()
            manager = getattr(model, 'all_objects', model._default_manager)
            private = model._meta.get_field(pf.field).storage
            names = manager.exclude(**{pf.field: ''}).exclude(**{f'{pf.field}__isnull': True}) \
                           .values_list(pf.field, flat=True)
            for name in names:
                if private.exists(name):
                    already += 1
                    continue
                if not default_storage.exists(name):
                    missing += 1
                    self.stderr.write(f'MISSING  {pf.model}.{pf.field}: {name}')
                    continue
                self.stdout.write(f'{"would move" if dry_run else "moving"}  {name}')
                if not dry_run:
                    with default_storage.open(name, 'rb') as f:
                        saved = private.save(name, f)
                    if saved != name:
                        raise RuntimeError(f'Private storage renamed {name} -> {saved}; aborting.')
                    default_storage.delete(name)
                moved += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"Would move" if dry_run else "Moved"} {moved}; already private {already}; missing {missing}.'))
