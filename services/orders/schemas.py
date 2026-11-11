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


Fulfillment = Literal["pickup", "delivery"]


class Checkout(Input):
    configuration_revision: int = Field(strict=True, gt=0, le=2147483647)
    catalog_revision: int = Field(strict=True, gt=0, le=2147483647)
    origin: Literal["client", "counter"]
    fulfillment: Fulfillment
    customer_name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, min_length=1, max_length=500)
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

    @field_validator("address", mode="before")
    @classmethod
    def trim_address(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def address_matches_fulfillment(self):
        if self.fulfillment == "delivery" and not self.address:
            raise ValueError("Informe o endereço de entrega.")

        if self.fulfillment != "delivery" and self.address is not None:
            raise ValueError("Endereço só é aceito em pedidos de entrega.")

        return self

    @model_validator(mode="after")
    def unique_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Envie cada produto apenas uma vez.")
        self.items.sort(key=lambda item: str(item.product_id))
        return self


class TransitionInput(Input):
    expected_version: int = Field(strict=True, gt=0, le=2147483647)
    target_state: Literal["preparing", "ready", "dispatched", "completed"]


class ItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    name: str
    unit_price_cents: int
    quantity: int
    subtotal_cents: int


class DeliveryDetails(BaseModel):
    """Read from Entregas on demand; `available=False` when it cannot answer now."""

    available: bool
    address: str | None = None
    dispatched_at: datetime | None = None


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
    delivery: DeliveryDetails | None = None
    dispatch_state: Literal["pending", "needs_attention"] | None = None


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
    fulfillment: str
    attempts: int
    created_at: datetime
    updated_at: datetime
    error: OperationError | None


class OperationPage(BaseModel):
    items: list[OperationSummary]
    next_cursor: str | None


class PendingDispatch(BaseModel):
    operation_id: UUID
    order_id: UUID
    state: Literal["pending", "needs_attention"]
    status_url: str


class DispatchSummary(BaseModel):
    operation_id: UUID
    order_id: UUID
    order_number: int
    customer_name: str | None
    state: Literal["pending", "succeeded", "needs_attention"]
    attempts: int
    created_at: datetime
    updated_at: datetime
    error: OperationError | None


class DispatchPage(BaseModel):
    items: list[DispatchSummary]
    next_cursor: str | None
