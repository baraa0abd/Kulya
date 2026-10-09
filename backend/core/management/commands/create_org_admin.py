"""Open an organization and its first administrator. Everything else is done from the app.

ADMIN_PASSWORD=... python manage.py create_org_admin "Shar Dialysis Unit" admin_username
"""

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from core.models import Organization, Role, User
from core.services import audit


class Command(BaseCommand):
    help = "Create an organization (if new) and an organization administrator account."

    def add_arguments(self, parser) -> None:
        parser.add_argument("organization")
        parser.add_argument("username")

    def handle(self, *args, **options) -> None:
        if User.objects.filter(username=options["username"]).exists():
            raise CommandError("That username is already taken.")
        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password for the administrator: ")
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        organization, _ = Organization.objects.get_or_create(name=options["organization"])
        admin = User.objects.create_user(
            options["username"], password=password, role=Role.ORG_ADMIN, organization=organization
        )
        audit(None, "org_admin_created", admin)
        self.stdout.write(self.style.SUCCESS(f"Administrator '{admin.username}' created for {organization.name}."))
