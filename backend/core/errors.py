"""One error shape for the whole API: {"error": {"code", "message", "details"}}. No stack traces,
no internal identifiers, no clinical content."""

from typing import Any

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(APIException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Any = None):
        super().__init__(detail=message, code=code)
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class Conflict(ApiError):
    def __init__(self, message: str, details: Any = None):
        super().__init__("invalid_state", message, 409, details)


def exception_handler(exc: Exception, context: dict) -> Response | None:
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ApiError):
        code, message, details = exc.code, str(exc.detail), exc.details
    else:
        data = response.data
        validation = response.status_code == 400 and not (isinstance(data, dict) and set(data) == {"detail"})
        fallback = {403: "permission_denied", 404: "not_found", 429: "throttled"}.get(response.status_code, "error")
        code = "validation_error" if validation else getattr(exc, "default_code", fallback)
        message = "Invalid input." if validation else str(data.get("detail", "Error"))
        details = data if validation else {}
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
