from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from chat.rag.index import index_directory


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--dir", default=None)

    def handle(self, *args, **options):
        if options["dir"]:
            directory = Path(options["dir"])
        else:
            directory = Path(settings.BASE_DIR) / "notes"
        for name, count in index_directory(directory):
            self.stdout.write(f"{name}: {count}")
