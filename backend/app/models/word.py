from sqlalchemy import Integer, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import TagType, WordType


class Word(TimestampMixin, Base):
    __tablename__ = "word"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("unit.id", ondelete="CASCADE"), nullable=False)
    english: Mapped[str] = mapped_column(String(500), nullable=False)
    chinese: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[WordType] = mapped_column(Enum(WordType), nullable=False, default=WordType.word)

    unit: Mapped["Unit"] = relationship(back_populates="words")  # noqa: F821
    tags: Mapped[list["WordTag"]] = relationship(back_populates="word", cascade="all, delete-orphan")
    mastery_records: Mapped[list["MasteryRecord"]] = relationship(back_populates="word", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Word(id={self.id}, english='{self.english}')>"


class WordTag(Base):
    __tablename__ = "word_tags"

    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("word.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[TagType] = mapped_column(Enum(TagType), primary_key=True)

    word: Mapped["Word"] = relationship(back_populates="tags")
