from django.core.management.base import BaseCommand

from nutrition.catalog import load_catalog


class Command(BaseCommand):
    help = "Load the bundled demo food and recipe catalogue (approximate, unverified values)."

    def handle(self, *args, **options) -> None:
        self.stdout.write(f"Loaded {load_catalog()} foods. These values are unverified demo data.")
