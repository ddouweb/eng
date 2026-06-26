from datetime import date, datetime

from sqlalchemy import Integer, Date, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PlanStatus, PlanType, TaskStatus, TaskType


class LearningPlan(TimestampMixin, Base):
    __tablename__ = "learning_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(nullable=False)
    daily_goal: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus), nullable=False, default=PlanStatus.active
    )
    # JSON 字符串，如 "[0,1,2,3,4]"；0=Mon..6=Sun
    learn_weekdays: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="[0,1,2,3,4]"
    )
    # None=不开月复习；1-28=每月固定日；31=月末（运行时按当月最后一天换算）
    monthly_review_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 计划生效起始日（默认今天）。二轮/三轮计划可设未来日期，不会立刻产出任务
    start_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    # forward=首轮学新词；review_only=二轮纯复习；wrong_word_drill=三轮错题刷
    plan_type: Mapped[PlanType] = mapped_column(
        Enum(PlanType), nullable=False, default=PlanType.forward, server_default="forward"
    )

    plan_units: Mapped[list["PlanUnit"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    daily_tasks: Mapped[list["DailyTask"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="DailyTask.task_date"
    )


class PlanUnit(Base):
    __tablename__ = "plan_units"

    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("learning_plan.id", ondelete="CASCADE"), primary_key=True
    )
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("unit.id", ondelete="CASCADE"), primary_key=True
    )

    plan: Mapped["LearningPlan"] = relationship(back_populates="plan_units")


class DailyTask(TimestampMixin, Base):
    __tablename__ = "daily_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("learning_plan.id", ondelete="CASCADE"), nullable=False
    )
    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.pending
    )
    task_type: Mapped[TaskType] = mapped_column(
        Enum(TaskType), nullable=False, default=TaskType.learn, server_default="learn"
    )

    plan: Mapped["LearningPlan"] = relationship(back_populates="daily_tasks")

    __table_args__ = (
        UniqueConstraint("plan_id", "task_date", "task_type", name="uk_plan_date_type"),
    )
