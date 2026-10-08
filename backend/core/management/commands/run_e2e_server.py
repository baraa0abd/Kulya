"""Keep browser-test writes out of the interactive demonstration database."""

import os

import psycopg
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.test.utils import override_settings
from psycopg import sql


class Command(BaseCommand):
    help = "Prepare a separate local *_e2e database and serve the offline browser-test API on port 8001."
    requires_system_checks = []

    def handle(self, *args, **options):
        config = settings.DATABASES["default"]
        if not settings.DEBUG or config["HOST"] not in {"localhost", "127.0.0.1", "::1"}:
            raise CommandError("Browser-test setup requires DEBUG and a local PostgreSQL server.")
        if not os.environ.get("DEMO_PASSWORD"):
            raise CommandError("Set DEMO_PASSWORD before preparing the browser-test database.")
        name = config["NAME"] if config["NAME"].endswith("_e2e") else config["NAME"] + "_e2e"
        with psycopg.connect(
            dbname="postgres",
            user=config["USER"],
            password=config["PASSWORD"],
            host=config["HOST"],
            port=config["PORT"],
            autocommit=True,
        ) as admin:
            if not admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        connections.close_all()
        connections.databases["default"]["NAME"] = name
        config["NAME"] = name
        rates = {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "login": "1000/min"}
        rest = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": rates}
        with override_settings(LLM_PROVIDER="mock", CELERY_TASK_ALWAYS_EAGER=True, REST_FRAMEWORK=rest):
            call_command("migrate", interactive=False, verbosity=0)
            call_command("seed_demo")
            self.stdout.write(f"Browser-test database: {name}. Interactive demo records are unchanged.")
            call_command("runserver", "127.0.0.1:8001", use_reloader=False)
