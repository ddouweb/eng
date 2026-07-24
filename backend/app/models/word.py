from sqlalchemy import Integer, Enum, ForeignKey, String, Text
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
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 富字段：让词条从「英中对译」升级为可学的语言单位（音标 / 英文释义 / 词性 / 例句）。
    # 全部 nullable —— 旧数据与手动录入无需提供；ECDICT 导入与 AI 解析按可用性回填。
    # 前端音标优先读 phonetic，缺省再回退 eng_to_ipa 运行时计算（保持旧行为）。
    phonetic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    definition: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pos: Mapped[str | None] = mapped_column(String(100), nullable=True)
    example: Mapped[str | None] = mapped_column(Text, nullable=True)

    unit: Mapped["Unit"] = relationship(back_populates="words")  # noqa: F821
    tags: Mapped[list["WordTag"]] = relationship(back_populates="word", cascade="all, delete-orphan")
    mastery_records: Mapped[list["MasteryRecord"]] = relationship(back_populates="word", cascade="all, delete-orphan")  # noqa: F821
    wrong_word_book: Mapped[list["WrongWordBook"]] = relationship(back_populates="word", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Word(id={self.id}, english='{self.english}')>"


class WordTag(Base):
    __tablename__ = "word_tags"

    word_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("word.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[TagType] = mapped_column(Enum(TagType), primary_key=True)

    word: Mapped["Word"] = relationship(back_populates="tags")
