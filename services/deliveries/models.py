from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        CheckConstraint("length(trim(address)) > 0", name="address_required"),
        CheckConstraint("fee_cents = 500", name="fixed_delivery_fee"),
        CheckConstraint("(transition_id IS NULL) = (dispatched_at IS NULL)", name="dispatch_fields_together"),
    )

    order_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    operation_id: Mapped[UUID] = mapped_column(Uuid, unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    fee_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    transition_id: Mapped[UUID | None] = mapped_column(Uuid, unique=True)
    dispatched_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
