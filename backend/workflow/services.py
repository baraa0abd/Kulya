from django.db import IntegrityError, transaction

from clinical.models import DialysisSession
from core.models import User

from .models import Notification


def notify(recipient: User, kind: str, title: str, session: DialysisSession | None, dedupe: str, patient=None) -> None:
    """Idempotent delivery: the same event never notifies the same person twice. Titles are generic
    on purpose; clinical detail stays behind the authorized API."""
    try:
        with transaction.atomic():
            Notification.objects.create(
                recipient=recipient,
                kind=kind,
                title=title,
                session=session,
                patient=session.patient if session else patient,
                dedupe_key=f"{dedupe}:{recipient.pk}",
            )
    except IntegrityError:
        pass
