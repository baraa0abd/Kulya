"""Shared error_format: {"error": {"code", "message_ar", "message_en", "details"}}."""

from typing import Any

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

MESSAGES_AR = {
    400: "البيانات المدخلة غير صحيحة.",
    401: "يجب تسجيل الدخول أولاً.",
    403: "ليست لديك صلاحية لهذا الإجراء.",
    404: "العنصر غير موجود.",
    405: "الطريقة غير مسموحة.",
    409: "الحالة الحالية لا تسمح بهذا الإجراء.",
    501: "هذه الخدمة غير متوفرة بعد.",
}
DEFAULT_MESSAGE_AR = "حدث خطأ غير متوقع."


class ApiError(APIException):
    """Raise from services/views for a contract-shaped error with an explicit Arabic message."""

    def __init__(self, code: str, message_ar: str, message_en: str, status_code: int = 400, details: Any = None):
        super().__init__(detail=message_en, code=code)
        self.status_code = status_code
        self.code = code
        self.message_ar = message_ar
        self.details = details or {}


def exception_handler(exc: Exception, context: dict) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ApiError):
        code, message_en, details, message_ar = exc.code, str(exc.detail), exc.details, exc.message_ar
    else:
        data = response.data
        is_validation = response.status_code == 400 and not (isinstance(data, dict) and set(data) == {"detail"})
        # Django's Http404 / PermissionDenied carry no DRF code; fall back on the status.
        by_status = {403: "permission_denied", 404: "not_found"}
        fallback = by_status.get(response.status_code, "error")
        code = "validation_error" if is_validation else getattr(exc, "default_code", fallback)
        message_en = "Invalid input." if is_validation else str(data.get("detail", "Error"))
        details = data if is_validation else {}
        message_ar = MESSAGES_AR.get(response.status_code, DEFAULT_MESSAGE_AR)
    response.data = {"error": {"code": code, "message_ar": message_ar, "message_en": message_en, "details": details}}
    return response
