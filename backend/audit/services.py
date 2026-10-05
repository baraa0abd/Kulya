"""Audit trail: who did what to which object, with before/after state."""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.forms.models import model_to_dict

from .models import AuditLog


def snapshot(obj: Model, *fields: str) -> dict:
    """JSON-safe copy of a model's fields (all concrete fields, or just the named ones)."""
    return json.loads(json.dumps(model_to_dict(obj, fields=fields or None), cls=DjangoJSONEncoder))


def log(actor: Model, action: str, obj: Model, before: dict | None = None, after: dict | None = None) -> AuditLog:
    """Call from every service that creates, approves, rejects, or edits a record."""
    return AuditLog.objects.create(
        actor=actor, action=action, object_type=type(obj).__name__, object_id=obj.pk, before=before, after=after
    )
