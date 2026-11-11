"""Orders, customer credentials and durable checkout progress owned by Pedidos."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Integer, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CustomerContext(Base):
    __tablename__ = "customer_contexts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    recovery_token_hash: Mapped[str | None] = mapped_column(String(64))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("origin IN ('client', 'counter', 'tablet')", name="valid_origin"),
        CheckConstraint("fulfillment IN ('pickup', 'delivery', 'table')", name="valid_fulfillment"),
        CheckConstraint("state IN ('received', 'preparing', 'ready', 'dispatched', 'completed')", name="valid_state"),
        CheckConstraint("state != 'dispatched' OR fulfillment = 'delivery'", name="dispatch_requires_delivery"),
        CheckConstraint("origin != 'tablet' OR fulfillment = 'table'", name="tablet_requires_table"),
        CheckConstraint("fulfillment != 'table' OR table_id IS NOT NULL", name="table_required"),
        CheckConstraint("origin = 'tablet' OR length(trim(customer_name)) > 0 AND customer_name IS NOT NULL", name="customer_required"),
        CheckConstraint("total_cents >= fee_cents AND fee_cents >= 0", name="valid_totals"),
        CheckConstraint("version > 0 AND configuration_revision > 0 AND catalog_revision > 0", name="positive_revisions"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    number: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True, nullable=False)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    fulfillment: Mapped[str] = mapped_column(String(10), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(120))
    customer_context_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_contexts.id"), index=True)
    table_id: Mapped[UUID | None] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(12), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    catalog_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    fee_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 99", name="valid_quantity"),
        CheckConstraint("unit_price_cents > 0", name="positive_item_price"),
        CheckConstraint("subtotal_cents = CAST(quantity AS BIGINT) * unit_price_cents", name="valid_subtotal"),
    )

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    product_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Transition(Base):
    __tablename__ = "transitions"
    __table_args__ = (UniqueConstraint("principal_id", "idempotency_key", name="unique_transition_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    previous_state: Mapped[str] = mapped_column(String(12), nullable=False)
    target_state: Mapped[str] = mapped_column(String(12), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    principal_id: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[UUID | None] = mapped_column(Uuid)
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CheckoutOperation(Base):
    __tablename__ = "checkout_operations"
    __table_args__ = (
        UniqueConstraint("principal_id", "idempotency_key", name="unique_checkout_key"),
        CheckConstraint("state IN ('pending', 'succeeded', 'rejected', 'needs_attention')", name="valid_operation_state"),
        CheckConstraint("attempts >= 0", name="valid_attempts"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    order_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    principal_id: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_context_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_contexts.id"))
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    admission: Mapped[dict | None] = mapped_column(JSON)
    quote: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[dict | None] = mapped_column(JSON)
    error_status: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    lease_id: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OperationResume(Base):
    __tablename__ = "operation_resumes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(ForeignKey("checkout_operations.id"), nullable=False)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
