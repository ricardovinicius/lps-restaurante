"""Tables, tablet credentials and validation receipts, owned by Mesas."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DiningTable(Base):
    __tablename__ = "dining_tables"
    __table_args__ = (
        CheckConstraint("number > 0", name="positive_table_number"),
        CheckConstraint("version > 0", name="positive_table_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class TableValidation(Base):
    """Immutable receipt that a table accepted one order operation."""

    __tablename__ = "table_validations"

    operation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    table_id: Mapped[UUID] = mapped_column(ForeignKey("dining_tables.id"), nullable=False)
    table_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TableContext(Base):
    """Tablet credential provisioned by an operator; only the token hash is stored."""

    __tablename__ = "table_contexts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    table_id: Mapped[UUID] = mapped_column(ForeignKey("dining_tables.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
