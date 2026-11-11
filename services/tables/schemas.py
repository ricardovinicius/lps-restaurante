from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mesa_platform.http import Input


class TableView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: int
    available: bool
    version: int


class TablePage(BaseModel):
    items: list[TableView]
    next_cursor: str | None


class AvailabilityUpdate(Input):
    expected_version: int = Field(strict=True, gt=0, le=2147483647)
    available: bool = Field(strict=True)


class ContextRequest(Input):
    table_id: UUID


class ContextView(BaseModel):
    context_id: UUID
    table_id: UUID
    table_number: int
    expires_at: datetime
    csrf_token: str


class ContextVerification(Input):
    token: str = Field(min_length=1, max_length=128)
    csrf_token: str | None = Field(default=None, max_length=128)


class VerifiedContext(BaseModel):
    context_id: UUID
    table_id: UUID
    table_number: int
    expires_at: datetime


class ValidationRequest(Input):
    table_id: UUID


class ValidationReceipt(BaseModel):
    operation_id: UUID
    table_id: UUID
    table_number: int
