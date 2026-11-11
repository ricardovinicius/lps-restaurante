from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mesa_platform.http import Input


class CustomerContextInput(Input):
    recovery_token: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    new_context: bool = Field(default=False, strict=True)


class CustomerRecovery(Input):
    context_id: UUID
    recovery_token: str = Field(pattern=r"^[a-f0-9]{64}$")


class CheckoutItem(Input):
    product_id: UUID
    quantity: int = Field(strict=True, ge=1, le=99)
    expected_unit_price_cents: int = Field(strict=True, gt=0, le=2147483647)


class Checkout(Input):
    configuration_revision: int = Field(strict=True, gt=0, le=2147483647)
    catalog_revision: int = Field(strict=True, gt=0, le=2147483647)
    origin: Literal["client", "counter"]
    fulfillment: Literal["pickup"]
    customer_name: str = Field(min_length=1, max_length=120)
    items: list[CheckoutItem] = Field(min_length=1, max_length=50)

    @field_validator("customer_name", mode="before")
    @classmethod
    def trim_name(cls, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("Informe seu nome.")
        return value

    @model_validator(mode="after")
    def unique_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Envie cada produto apenas uma vez.")
        self.items.sort(key=lambda item: str(item.product_id))
        return self


class TransitionInput(Input):
    expected_version: int = Field(strict=True, gt=0, le=2147483647)
    target_state: Literal["preparing", "ready", "completed"]


class ItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    unit_price_cents: int
    quantity: int
    subtotal_cents: int


class OrderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: int
    origin: str
    fulfillment: str
    customer_name: str | None
    state: str
    version: int
    configuration_revision: int
    catalog_revision: int
    items: list[ItemView]
    fee_cents: int
    total_cents: int
    created_at: datetime
    updated_at: datetime


class OrderPage(BaseModel):
    items: list[OrderView]
    next_cursor: str | None


class OperationError(BaseModel):
    code: str
    message: str
    details: dict | list | None = None


class OperationView(BaseModel):
    operation_id: UUID
    state: Literal["pending", "succeeded", "rejected", "needs_attention"]
    order: OrderView | None = None
    error: OperationError | None = None


class PendingOperation(BaseModel):
    operation_id: UUID
    state: Literal["pending", "needs_attention"]
    status_url: str


class OperationSummary(BaseModel):
    operation_id: UUID
    idempotency_key: UUID
    state: str
    customer_name: str
    origin: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    error: OperationError | None


class OperationPage(BaseModel):
    items: list[OperationSummary]
    next_cursor: str | None
