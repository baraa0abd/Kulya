"""The record assistant's workflow: collect what the patient may already see, ask, check, store."""

from datetime import timedelta

from django.utils import timezone

from ai.gateway import call_model
from ai.models import AISummary
from clinical.models import Patient, SessionStatus
from core.models import User
from core.services import audit
from nutrition import services as nutrition
from nutrition.models import ReviewStatus

from .ai import CHAT, mock_answer, validate_answer
from .models import ChatMessage


def record_facts(patient: Patient) -> dict:
    """Everything the assistant may use, all of it already visible to the patient."""
    today, now = timezone.localdate(), timezone.now()
    plan = nutrition.active_plan(patient)
    upcoming = patient.sessions.filter(status=SessionStatus.SCHEDULED, scheduled_start__gte=now)
    summaries = (
        AISummary.objects.filter(session__patient=patient, released=True, status=AISummary.Status.VERIFIED)
        .select_related("session")
        .order_by("-session__scheduled_start")
    )
    ideas = patient.meal_recommendations.filter(review_status=ReviewStatus.APPROVED).select_related("recipe")
    return {
        "today": today.isoformat(),
        "laboratory_results": nutrition.lab_facts(patient, today - timedelta(days=365), today, released_only=True),
        "upcoming_sessions": [
            timezone.localtime(s.scheduled_start).strftime("%Y-%m-%d %H:%M")
            for s in upcoming.order_by("scheduled_start")[:3]
        ],
        "released_summaries": [
            {
                "session_date": timezone.localtime(s.session.scheduled_start).date().isoformat(),
                "text": s.output.get("patient_summary", ""),
            }
            for s in summaries[:3]
        ],
        "nutrition_plan": {
            "guidance": plan.guidance,
            "prescribed_targets": plan.prescribed_targets,
            "allergies": plan.allergies,
        }
        if plan
        else None,
        "diary_today": nutrition.diary(patient, today, today),
        "diary_last_7_days": nutrition.diary(patient, today - timedelta(days=6), today),
        "approved_meal_ideas": [
            {"name": name, "name_ar": name_ar}
            for name, name_ar in dict.fromkeys(
                (i.recipe.name, i.recipe.localized_names.get("ar", i.recipe.name)) for i in ideas[:20]
            )
        ][:5],
    }


def answer(patient: Patient, user: User, question: str, language: str) -> ChatMessage:
    history = ChatMessage.objects.filter(patient=patient).order_by("-created_at")[:5]
    payload = {
        "question": question,
        "language": language,
        "history": [{"question": m.question, "answer": m.answer} for m in reversed(history)],
        "record": record_facts(patient),
    }
    output, errors, model_name = call_model(CHAT, payload)
    if output is not None:
        errors = validate_answer(output, payload)
    if errors:  # provider down, or it said something outside its role: answer from the rules instead
        output, model_name = {"answer": mock_answer(payload)}, "rule-based"
    message = ChatMessage.objects.create(
        patient=patient, author=user, question=question, answer=output["answer"], model_name=model_name
    )
    audit(user, "assistant_question", message, patient=patient, model=model_name)
    return message
