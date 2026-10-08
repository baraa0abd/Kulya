"""Celery entry points. Both are idempotent by data fingerprint (see services), so redelivery is safe."""

from datetime import date

from celery import shared_task

from . import services


@shared_task(name="nutrition.analyze", ignore_result=True)
def analyze(patient_id: str, start: str, end: str) -> None:
    services.analyze(patient_id, date.fromisoformat(start), date.fromisoformat(end))


@shared_task(name="nutrition.build_report", ignore_result=True)
def build_report(patient_id: str, start: str, end: str) -> None:
    services.build_report(patient_id, date.fromisoformat(start), date.fromisoformat(end))
