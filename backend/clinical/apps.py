import sys
import warnings

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError, ProgrammingError

SKIP_GUARD_COMMANDS = {"migrate", "makemigrations", "showmigrations", "sqlmigrate"}


def check_demo_guard() -> None:
    """DEMO_MODE must never run on real patient data."""
    from .models import Patient

    if settings.DEMO_MODE and Patient.objects.filter(is_synthetic=False).exists():
        raise ImproperlyConfigured(
            "DEMO_MODE is on but the database contains a Patient with is_synthetic=False. "
            "The demo may only run on synthetic data; remove that record or turn DEMO_MODE off."
        )


class ClinicalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "clinical"

    def ready(self) -> None:
        if SKIP_GUARD_COMMANDS & set(sys.argv):
            return
        try:
            with warnings.catch_warnings():
                # Django discourages DB access during app init; this startup check is the exception.
                warnings.simplefilter("ignore", RuntimeWarning)
                check_demo_guard()
        except (OperationalError, ProgrammingError):
            pass  # no database or tables yet (first run before `migrate`)
