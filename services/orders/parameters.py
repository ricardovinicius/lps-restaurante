"""Request parameters and staff dependencies shared by the Pedidos routers."""

from typing import Annotated
from uuid import UUID

from fastapi import Header, Query, Request

from mesa_platform.access import authorize_staff

IdempotencyKey = Annotated[UUID, Header(alias="Idempotency-Key")]
PageSize = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=160)]


def operator(request: Request):
    return authorize_staff(request, "operator")


def operator_mutation(request: Request):
    return authorize_staff(request, "operator", require_csrf=True)
