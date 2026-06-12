from datetime import date, datetime

from sqlalchemy import Integer, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PlanStatus, TaskStatus


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

    plan: Mapped["LearningPlan"] = relationship(back_populates="daily_tasks")

    __table_args__ = (UniqueConstraint("plan_id", "task_date", name="uk_plan_date"),)
