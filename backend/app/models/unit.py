from sqlalchemy import BIGINT, Int, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Unit(TimestampMixin, Base):
    __tablename__ = "unit"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(Int, nullable=False, unique=True, default=0)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    words: Mapped[list["Word"]] = relationship(back_populates="unit", cascade="all, delete-orphan", order_by="Word.id")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Unit(id={self.id}, title='{self.title}', seq={self.sequence})>"
