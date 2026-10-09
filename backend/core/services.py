"""Cross-cutting helpers (audit trail, background-task dispatch, idempotent POST handling) and
the account use cases."""

import json
import logging
from collections.abc import Callable

from django.conf import settings
from django.db import IntegrityError, models
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response

from .models import AuditEvent, IdempotencyKey, User

logger = logging.getLogger("kulya")


def audit(actor: User | None, action: str, obj: models.Model | None = None, patient=None, **metadata) -> AuditEvent:
    """Record who did what. `metadata` must hold ids and states only, never clinical free text."""
    patient_id = getattr(patient, "pk", None) or getattr(obj, "patient_id", None)
    return AuditEvent.objects.create(
        actor=actor,
        organization_id=getattr(actor, "organization_id", None),
        action=action,
        object_type=type(obj).__name__ if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        patient_id=patient_id,
        metadata=metadata,
    )


def dispatch(task, *args) -> bool:
    """Queue a Celery task. Returns False (and logs) when the broker is unreachable, so a clinical
    write never fails because the worker or Redis is down."""
    try:
        if settings.CELERY_TASK_ALWAYS_EAGER:
            task.apply(args=args)
        else:
            task.apply_async(args=args, retry=False)
        return True
    except Exception:  # broker/worker failure must not break the request
        logger.exception("task dispatch failed", extra={"ctx": {"task": task.name}})
        return False


def idempotent(request: Request, handler: Callable[[], Response]) -> Response:
    """Replay the stored response when the same user retries a POST with the same Idempotency-Key."""
    key = request.headers.get("Idempotency-Key", "")[:100]
    if not key:
        return handler()
    lookup = {"key": key, "user": request.user, "path": request.path}
    stored = IdempotencyKey.objects.filter(**lookup).first()
    if stored:
        return Response(stored.response, status=stored.status_code)
    response = handler()
    if response.status_code < 500:
        try:
            body = json.loads(JSONRenderer().render(response.data))  # UUIDs, dates -> plain JSON
            IdempotencyKey.objects.create(**lookup, status_code=response.status_code, response=body)
        except IntegrityError:  # a concurrent retry stored it first
            pass
    return response


def create_account(admin: User, data: dict) -> User:
    """A new account always joins the administrator's own organization."""
    account = User.objects.create_user(organization=admin.organization, **data)
    audit(admin, "account_created", account, role=account.role)
    return account


def deactivate_account(admin: User, account: User) -> User:
    account.is_active = False
    account.save()
    audit(admin, "account_deactivated", account)
    return account


def change_password(user: User, new_password: str) -> None:
    user.set_password(new_password)
    user.save()
    audit(user, "password_changed", user)
