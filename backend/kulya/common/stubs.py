"""501 stubs that freeze the API contract in OpenAPI until the owning role implements each endpoint."""

from collections.abc import Callable

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from .errors import NotImplementedYet


def stub(
    name: str,
    response: type,
    *,
    method: str = "get",
    request: type | None = None,
    many: bool = False,
    roles: str = "",
    query: tuple[str, ...] = (),
) -> Callable:
    def handler(self: APIView, request: Request, **kwargs: int) -> None:
        raise NotImplementedYet()

    handler = extend_schema(
        operation_id=name,
        description=f"Allowed roles: {roles}. Not implemented yet (501).",
        request=request,
        responses=response(many=True) if many else response,
        parameters=[OpenApiParameter(q, str, required=False) for q in query],
    )(handler)
    return type(name, (APIView,), {method: handler}).as_view()
