"""Celery entry points. Both tasks are idempotent (see ai.services), so redelivery is safe."""

from celery import shared_task

from . import services


@shared_task(name="ai.review_session", ignore_result=True)
def review_session(session_id: str, trigger: str, nonce: str = "") -> None:
    services.run_review(session_id, trigger, nonce)


@shared_task(name="ai.summarize_session", ignore_result=True)
def summarize_session(session_id: str, requested_by_id: str | None = None, force: bool = False) -> None:
    services.run_summary(session_id, requested_by_id, force)
