from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Member(TimestampMixin, Base):
    __tablename__ = "member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)

    mastery_records: Mapped[list["MasteryRecord"]] = relationship(back_populates="member", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Member(id={self.id}, name='{self.name}')>"
