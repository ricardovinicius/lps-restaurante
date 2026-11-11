from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Integer, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DiningTable(Base):
    __tablename__ = "dining_tables"
    __table_args__ = (CheckConstraint("number > 0", name="positive_table_number"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
