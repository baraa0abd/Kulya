"""Input partitions and persistence checks for screen-facing API forms."""

from decimal import Decimal

import pytest
from django.utils import timezone

from clinical.models import VITAL_SPECS, VitalSign
from clinical.serializers import CompleteSessionSerializer, StartSessionSerializer
from tests.conftest import post_vital


@pytest.mark.parametrize("kind", list(VITAL_SPECS))
@pytest.mark.parametrize("boundary", ["low", "high", "below", "above"])
def test_vital_boundaries(api, nurse, in_progress, kind, boundary):
    unit, low, high = VITAL_SPECS[kind]
    value = {"low": low, "high": high, "below": low - 1, "above": high + 1}[boundary]
    before = VitalSign.objects.filter(session=in_progress).count()
    response = post_vital(api(nurse), in_progress, kind, value, "intra")
    valid = boundary in {"low", "high"}
    assert response.status_code == (201 if valid else 400), response.content
    assert VitalSign.objects.filter(session=in_progress).count() == before + int(valid)
    if valid:
        assert response.json()["unit"] == unit
        assert Decimal(response.json()["value"]) == value


@pytest.mark.parametrize("value", ["", " ", "abc", "NaN", "Infinity", None])
def test_invalid_measurement_does_not_persist(api, nurse, in_progress, value):
    response = post_vital(api(nurse), in_progress, "weight", value, "pre")
    assert response.status_code == 400
    assert not VitalSign.objects.filter(session=in_progress).exists()


@pytest.mark.parametrize(
    "endpoint,field,extra",
    [
        ("nursing-notes", "text", {}),
        ("nursing-actions", "description", {"action_type": "access_care", "performed_at": "now"}),
        ("session-events", "description", {"event_type": "incident", "occurred_at": "now"}),
    ],
)
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_documentation_is_rejected(api, nurse, in_progress, endpoint, field, extra, value):
    body = {"session": str(in_progress.id), field: value, **extra}
    body = {key: timezone.now().isoformat() if val == "now" else val for key, val in body.items()}
    response = api(nurse).post(f"/api/{endpoint}/", body, format="json")
    assert response.status_code == 400, response.content


@pytest.mark.parametrize(
    "serializer,field,values",
    [
        (StartSessionSerializer, "pre_weight_kg", [20, 300]),
        (CompleteSessionSerializer, "post_weight_kg", [20, 300]),
        (CompleteSessionSerializer, "uf_volume_ml", [0, 10000]),
    ],
)
def test_session_form_inclusive_boundaries(serializer, field, values):
    for value in values:
        instance = serializer(data={field: value})
        assert instance.is_valid(), instance.errors
    assert serializer(data={}).is_valid()  # missing is allowed, never invented as zero


@pytest.mark.parametrize(
    "serializer,field,values",
    [
        (StartSessionSerializer, "pre_weight_kg", [19, 301, "abc", None]),
        (CompleteSessionSerializer, "post_weight_kg", [19, 301, "abc", None]),
        (CompleteSessionSerializer, "uf_volume_ml", [-1, 10001, 1.5, "abc", None]),
    ],
)
def test_session_form_invalid_inputs(serializer, field, values):
    for value in values:
        instance = serializer(data={field: value})
        assert not instance.is_valid(), (field, value)
