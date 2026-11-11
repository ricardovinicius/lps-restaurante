"""Configuration data, owned exclusively by this service."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EstablishmentConfiguration(Base):
    __tablename__ = "configuration"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_establishment"),
        CheckConstraint("revision > 0", name="positive_revision"),
        CheckConstraint("pickup OR delivery OR tables", name="at_least_one_fulfillment"),
        CheckConstraint("NOT tablet OR tables", name="tablet_requires_tables"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    pickup: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tables: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tablet: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tv: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StaffUser(Base):
    __tablename__ = "staff_users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'operator')", name="staff_role"),)

    username: Mapped[str] = mapped_column(String(80), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(161), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)


class StaffSession(Base):
    __tablename__ = "staff_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(ForeignKey("staff_users.username", ondelete="CASCADE"))
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
