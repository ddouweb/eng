from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, PlanStatus, PlanType, TaskStatus
from app.models.mastery import MasteryRecord
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.practice import PracticeRecord, PracticeSession
from app.models.word import Word


class StatsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_mastery_distribution(self, member_id: int) -> dict[str, int]:
        # LEFT JOIN Word → MasteryRecord：从未练过的词无记录，COALESCE 计为 unlearned，
        # 使分布的 unlearned 桶如实反映"未学"词数（原先几乎恒为 0，与 mastery_rate 口径矛盾）。
        level_expr = func.coalesce(MasteryRecord.level, MasteryLevel.unlearned).label("level")
        stmt = (
            select(level_expr, func.count())
            .select_from(Word)
            .outerjoin(
                MasteryRecord,
                (MasteryRecord.word_id == Word.id) & (MasteryRecord.member_id == member_id),
            )
            .group_by(level_expr)
        )
        result = await self.session.execute(stmt)
        counts: dict[str, int] = {}
        for row in result.all():
            lvl = row[0]
            key = lvl.value if hasattr(lvl, "value") else str(lvl)
            counts[key] = row[1]
        for level in ("unlearned", "learning", "familiar", "permanent"):
            counts.setdefault(level, 0)
        return counts

    async def get_mastery_by_unit(self, member_id: int, unit_id: int) -> dict[str, int]:
        # 同上：按 unit 范围 LEFT JOIN，未练过的词计 unlearned
        level_expr = func.coalesce(MasteryRecord.level, MasteryLevel.unlearned).label("level")
        stmt = (
            select(level_expr, func.count())
            .select_from(Word)
            .outerjoin(
                MasteryRecord,
                (MasteryRecord.word_id == Word.id) & (MasteryRecord.member_id == member_id),
            )
            .where(Word.unit_id == unit_id)
            .group_by(level_expr)
        )
        result = await self.session.execute(stmt)
        counts: dict[str, int] = {}
        for row in result.all():
            lvl = row[0]
            key = lvl.value if hasattr(lvl, "value") else str(lvl)
            counts[key] = row[1]
        for level in ("unlearned", "learning", "familiar", "permanent"):
            counts.setdefault(level, 0)
        return counts

    async def get_total_word_count(self, unit_id: int | None = None) -> int:
        stmt = select(func.count()).select_from(Word)
        if unit_id is not None:
            stmt = stmt.where(Word.unit_id == unit_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_practice_summary(self, member_id: int) -> dict:
        stmt = select(
            func.count(PracticeSession.id),
            func.coalesce(func.sum(PracticeSession.total_count), 0),
            func.coalesce(func.sum(PracticeSession.correct_count), 0),
        ).where(PracticeSession.member_id == member_id, PracticeSession.ended_at.isnot(None))
        result = await self.session.execute(stmt)
        row = result.one()
        return {"session_count": row[0], "total_questions": row[1], "total_correct": row[2]}

    async def get_recent_practice_daily(self, member_id: int, days: int = 30) -> list[dict]:
        since_dt = datetime.combine(date.today() - timedelta(days=days), time.min)
        day_col = func.date(PracticeSession.started_at).label("day")
        stmt = (
            select(
                day_col,
                func.sum(PracticeSession.total_count).label("total"),
                func.sum(PracticeSession.correct_count).label("correct"),
            )
            .where(
                PracticeSession.member_id == member_id,
                PracticeSession.started_at >= since_dt,
            )
            .group_by(func.date(PracticeSession.started_at))
            .order_by(func.date(PracticeSession.started_at))
        )
        result = await self.session.execute(stmt)
        rows = []
        for row in result.all():
            d = row[0]
            if isinstance(d, str):
                d = date.fromisoformat(d)
            rows.append({"date": str(d), "total": int(row[1]), "correct": int(row[2])})
        return rows

    async def get_streak(self, member_id: int) -> int:
        stmt = (
            select(func.date(PracticeSession.started_at).label("day"))
            .where(PracticeSession.member_id == member_id)
            .group_by(func.date(PracticeSession.started_at))
            .order_by(func.date(PracticeSession.started_at).desc())
            .limit(400)
        )
        result = await self.session.execute(stmt)
        days = set()
        for row in result.all():
            d = row[0]
            if isinstance(d, str):
                d = date.fromisoformat(d)
            days.add(d)
        if not days:
            return 0

        streak = 0
        check = date.today()
        if check not in days:
            check -= timedelta(days=1)
        while check in days:
            streak += 1
            check -= timedelta(days=1)
        return streak

    # ─────────────────────────────────────────────────────
    # 每周结算（weekly settlement）的周聚合查询
    # 区间统一为 [ws, we] 闭区间（ws=周一, we=周日）。
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _week_bounds(ws: date, we: date) -> tuple[datetime, datetime]:
        """[ws, we] 闭区间 → [ws 00:00, (we+1) 00:00) 半开 datetime 区间。"""
        return datetime.combine(ws, time.min), datetime.combine(we + timedelta(days=1), time.min)

    async def get_week_active_days(self, member_id: int, ws: date, we: date) -> int:
        """本周真实学习日数 = COUNT DISTINCT DATE(practice_record.created_at)。

        与 _advance_streak 同源（submit 一题即推进 streak），故用 PracticeRecord 而非
        practice_session.ended_at——中途关掉的会话 ended_at=null 会漏算，导致
        "连续7天但 login 分低"的诡异。practice_record.created_at 已有索引（迁移 013）。
        """
        start_dt, end_dt = self._week_bounds(ws, we)
        stmt = (
            select(func.count(func.distinct(func.date(PracticeRecord.created_at))))
            .select_from(PracticeRecord)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .where(
                PracticeSession.member_id == member_id,
                PracticeRecord.created_at >= start_dt,
                PracticeRecord.created_at < end_dt,
            )
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def get_week_correct_breakdown(self, member_id: int, ws: date, we: date) -> dict:
        """本周答对的词聚合：难词数 / 答对词数（均 DISTINCT word_id，防多 tag 放大）。

        难词 = wrong_count≥2 AND ease_factor<2.3（收紧的高置信"卡壳词"）。
        level 是结算时刻终态，故仅用 wrong_count/ease 这两个客观难度信号。
        """
        start_dt, end_dt = self._week_bounds(ws, we)
        hard_cond = and_(
            MasteryRecord.wrong_count >= 2,
            MasteryRecord.ease_factor < 2.3,
        )
        stmt = (
            select(
                func.count(func.distinct(PracticeRecord.word_id)).label("correct_words"),
                func.count(
                    func.distinct(case((hard_cond, PracticeRecord.word_id)))
                ).label("hard_words"),
            )
            .select_from(PracticeRecord)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .outerjoin(
                MasteryRecord,
                (MasteryRecord.word_id == PracticeRecord.word_id)
                & (MasteryRecord.member_id == member_id),
            )
            .where(
                PracticeSession.member_id == member_id,
                PracticeRecord.is_correct.is_(True),
                PracticeRecord.created_at >= start_dt,
                PracticeRecord.created_at < end_dt,
            )
        )
        row = (await self.session.execute(stmt)).one()
        return {"correct_words": int(row[0] or 0), "hard_words": int(row[1] or 0)}

    async def get_week_new_word_count(self, member_id: int, ws: date, we: date) -> int:
        """本周首考的新词数 = COUNT word WHERE 该词全期首条 record.created_at 落本周。

        同源 _classify_attempt 的"首考"语义（聚合版）：prior_cnt==0 ⟺ 首条记录在该词之前不存在。
        """
        start_dt, end_dt = self._week_bounds(ws, we)
        first_seen = (
            select(
                PracticeRecord.word_id.label("wid"),
                func.min(PracticeRecord.created_at).label("first_at"),
            )
            .select_from(PracticeRecord)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .where(PracticeSession.member_id == member_id)
            .group_by(PracticeRecord.word_id)
        ).subquery()
        stmt = (
            select(func.count())
            .select_from(first_seen)
            .where(first_seen.c.first_at >= start_dt, first_seen.c.first_at < end_dt)
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def get_week_task_stats(self, member_id: int, ws: date, we: date) -> dict:
        """本周 active **forward** 计划的 DailyTask 完成统计。

        只计 plan_type=forward（与 get_active_forward_plan_with_remaining / plan_health 同源）：
        review_only / wrong_word_drill 的任务槽几乎全是已掌握词的复习，逐题已发 XP，
        若再计入 plan_score 会双重奖励复习、稀释"守约考研进度"语义。

        返回 completed_slots / planned_slots（Σ 槽位，零槽任务自然不计入分母）/ tasks_done / tasks_due。
        """
        stmt = (
            select(
                func.coalesce(
                    func.sum(DailyTask.completed_new + DailyTask.completed_review), 0
                ).label("completed_slots"),
                func.coalesce(
                    func.sum(DailyTask.new_count + DailyTask.review_count), 0
                ).label("planned_slots"),
                func.count().label("tasks_due"),
                func.coalesce(
                    func.sum(case((DailyTask.status == TaskStatus.completed, 1), else_=0)), 0
                ).label("tasks_done"),
            )
            .select_from(DailyTask)
            .join(LearningPlan, LearningPlan.id == DailyTask.plan_id)
            .where(
                LearningPlan.member_id == member_id,
                LearningPlan.status == PlanStatus.active,
                LearningPlan.plan_type == PlanType.forward,
                DailyTask.task_date >= ws,
                DailyTask.task_date <= we,
            )
        )
        row = (await self.session.execute(stmt)).one()
        return {
            "completed_slots": int(row[0] or 0),
            "planned_slots": int(row[1] or 0),
            "tasks_due": int(row[2] or 0),
            "tasks_done": int(row[3] or 0),
        }

    async def get_active_forward_plan_with_remaining(self, member_id: int) -> dict | None:
        """取该 member 最近一个 active forward 计划，返回 plan_health 所需输入；无则 None。

        remaining_unmastered 口径与 plan_service._generate_tasks 完全一致：
        total_words(plan_units) − mastered(level∈{familiar,permanent})。
        """
        plan = (
            await self.session.execute(
                select(LearningPlan)
                .where(
                    LearningPlan.member_id == member_id,
                    LearningPlan.status == PlanStatus.active,
                    LearningPlan.plan_type == PlanType.forward,
                )
                .order_by(LearningPlan.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if plan is None:
            return None
        unit_ids = [
            r[0] for r in (
                await self.session.execute(
                    select(PlanUnit.unit_id).where(PlanUnit.plan_id == plan.id)
                )
            ).all()
        ]
        if not unit_ids:
            total_words = 0
            mastered = 0
        else:
            total_words = int(
                (await self.session.execute(
                    select(func.count()).select_from(Word).where(Word.unit_id.in_(unit_ids))
                )).scalar_one()
            )
            mastered = int(
                (await self.session.execute(
                    select(func.count())
                    .select_from(MasteryRecord)
                    .join(Word, Word.id == MasteryRecord.word_id)
                    .where(
                        Word.unit_id.in_(unit_ids),
                        MasteryRecord.member_id == member_id,
                        MasteryRecord.level.in_(
                            [MasteryLevel.familiar, MasteryLevel.permanent]
                        ),
                    )
                )).scalar_one()
            )
        return {
            "plan_id": plan.id,
            "deadline": plan.deadline,
            "daily_goal": plan.daily_goal,
            "learn_weekdays_raw": plan.learn_weekdays,
            "total_words": total_words,
            "mastered": mastered,
        }
