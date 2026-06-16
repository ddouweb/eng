import random
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, PlanStatus, PracticeMode, TagType, TaskStatus
from app.models.mastery import MasteryRecord
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.practice import PracticeRecord, PracticeSession
from app.models.word import Word, WordTag
from app.repositories.mastery_repo import MasteryRepo
from app.repositories.practice_repo import PracticeRecordRepo, PracticeSessionRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException
from app.utils.weighting import compute_weight, weighted_sample


class PracticeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_repo = PracticeSessionRepo(session)
        self.record_repo = PracticeRecordRepo(session)
        self.mastery_repo = MasteryRepo(session)

    async def start_practice(
        self, member_id: int, mode: PracticeMode,
        unit_ids: list[int], count: int = 10,
    ) -> dict:
        questions = await self._build_questions(member_id, unit_ids, count)
        if not questions:
            raise AppException(400, "没有可练习的单词")

        ps = PracticeSession(
            member_id=member_id,
            mode=mode,
            total_count=len(questions),
        )
        ps = await self.session_repo.create(ps)
        await self.session.commit()
        await self.session.refresh(ps)

        for i, q in enumerate(questions):
            q["question_id"] = i

        if mode == PracticeMode.choice:
            for q in questions:
                q["options"] = await self._generate_options(q, questions)

        return success(data={
            "session_id": ps.id,
            "mode": ps.mode.value,
            "total": ps.total_count,
            "questions": questions,
        })

    async def submit_answer(
        self, session_id: int, word_id: int,
        is_correct: bool, user_answer: str | None = None,
    ) -> dict:
        ps = await self.session_repo.get_by_id(session_id)
        if not ps:
            raise AppException(404, "Practice session not found")
        if ps.ended_at:
            raise AppException(400, "Session already ended")

        word = await self.session.get(Word, word_id)
        if not word:
            raise AppException(404, "Word not found")

        # 在插入 PracticeRecord 之前先判定：
        #   - is_first_today: 该词今天是否还没有任何练习记录（避免同一天重复回流）
        #   - is_new_word:    该词在今天之前从未被练过 → 新词；否则复习词
        today = date.today()
        is_first_today, is_new_word = await self._classify_attempt(ps.member_id, word_id, today)

        record = PracticeRecord(
            session_id=session_id,
            word_id=word_id,
            is_correct=is_correct,
            user_answer=user_answer,
        )
        await self.record_repo.create(record)

        if is_correct:
            ps.correct_count += 1

        mastery = await self._update_mastery(ps.member_id, word_id, is_correct)

        # 答对 + 今天首次 → 回流到对应 active plan 的今日任务
        if is_correct and is_first_today:
            await self._tick_daily_task(ps.member_id, word.unit_id, today, is_new_word)

        await self.session.commit()

        return success(data={
            "is_correct": is_correct,
            "correct_answer": word.english,
            "mastery": {
                "level": mastery.level.value,
                "consecutive_correct": mastery.consecutive_correct,
                "correct_count": mastery.correct_count,
                "wrong_count": mastery.wrong_count,
            },
        })

    async def finish_practice(self, session_id: int) -> dict:
        ps = await self.session_repo.get_by_id(session_id)
        if not ps:
            raise AppException(404, "Practice session not found")
        if ps.ended_at:
            raise AppException(400, "Session already ended")

        ps.ended_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(ps)

        accuracy = (ps.correct_count / ps.total_count * 100) if ps.total_count > 0 else 0

        return success(data={
            "session_id": ps.id,
            "mode": ps.mode.value,
            "total_count": ps.total_count,
            "correct_count": ps.correct_count,
            "accuracy": round(accuracy, 1),
            "started_at": ps.started_at.isoformat() if ps.started_at else None,
            "ended_at": ps.ended_at.isoformat() if ps.ended_at else None,
        })

    async def get_session(self, session_id: int) -> dict:
        ps = await self.session_repo.get_by_id(session_id)
        if not ps:
            raise AppException(404, "Practice session not found")
        records = await self.record_repo.get_by_session(session_id)
        return success(data={
            "session_id": ps.id,
            "mode": ps.mode.value,
            "total_count": ps.total_count,
            "correct_count": ps.correct_count,
            "status": "completed" if ps.ended_at else "in_progress",
            "records": [
                {
                    "word_id": r.word_id,
                    "is_correct": r.is_correct,
                    "user_answer": r.user_answer,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ],
        })

    async def _build_questions(self, member_id: int, unit_ids: list[int], count: int) -> list[dict]:
        stmt = (
            select(Word, WordTag.tag)
            .outerjoin(WordTag, WordTag.word_id == Word.id)
            .where(Word.unit_id.in_(unit_ids))
        )
        result = await self.session.execute(stmt)
        word_tags: dict[int, tuple[Word, list[TagType]]] = {}
        for word, tag in result.all():
            if word.id not in word_tags:
                word_tags[word.id] = (word, [])
            if tag:
                word_tags[word.id][1].append(tag)

        stmt_m = select(MasteryRecord).where(
            MasteryRecord.member_id == member_id,
            MasteryRecord.word_id.in_(word_tags.keys()),
        )
        result_m = await self.session.execute(stmt_m)
        mastery_map: dict[int, MasteryRecord] = {r.word_id: r for r in result_m.scalars().all()}

        candidates = []
        for wid, (word, tags) in word_tags.items():
            mastery = mastery_map.get(wid)
            level = mastery.level if mastery else MasteryLevel.unlearned
            w = compute_weight(level, tags)
            if w > 0:
                candidates.append({
                    "word_id": word.id,
                    "english": word.english,
                    "chinese": word.chinese,
                    "type": word.type.value,
                    "weight": w,
                    "tags": [t.value for t in tags],
                    "mastery_level": level.value,
                })

        return weighted_sample(candidates, count)

    async def _generate_options(self, correct: dict, all_questions: list[dict]) -> list[str]:
        candidates = [q["chinese"] for q in all_questions if q["word_id"] != correct["word_id"]]
        if len(candidates) < 3:
            candidates.extend(["(无选项)"] * (3 - len(candidates)))
        wrong = random.sample(candidates, min(3, len(candidates)))
        options = wrong + [correct["chinese"]]
        random.shuffle(options)
        return options

    async def _update_mastery(self, member_id: int, word_id: int, is_correct: bool) -> MasteryRecord:
        record = await self.mastery_repo.get_or_create(member_id, word_id)

        if is_correct:
            record.correct_count += 1
            record.consecutive_correct += 1
            record = self._try_upgrade(record)
        else:
            record.wrong_count += 1
            record.consecutive_correct = 0
            record = self._try_downgrade(record)

        await self.session.flush()
        return record

    @staticmethod
    def _try_upgrade(record: MasteryRecord) -> MasteryRecord:
        if record.level == MasteryLevel.unlearned:
            record.level = MasteryLevel.learning
        elif record.level == MasteryLevel.learning and record.consecutive_correct >= 3:
            record.level = MasteryLevel.familiar
        elif (
            record.level == MasteryLevel.familiar
            and record.consecutive_correct >= 5
            and record.correct_count >= 8
        ):
            record.level = MasteryLevel.permanent
        return record

    @staticmethod
    def _try_downgrade(record: MasteryRecord) -> MasteryRecord:
        if record.level == MasteryLevel.familiar:
            record.level = MasteryLevel.learning
        elif record.level == MasteryLevel.permanent and record.wrong_count >= 2:
            record.level = MasteryLevel.familiar
        return record

    async def _classify_attempt(
        self, member_id: int, word_id: int, today: date,
    ) -> tuple[bool, bool]:
        """返回 (is_first_today, is_new_word)。

        is_first_today: 该词今天还没有任何 PracticeRecord（在本次提交之前）。
        is_new_word:   该词在今天之前从未被练过。
        """
        base = (
            select(func.count())
            .select_from(PracticeRecord)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .where(
                PracticeRecord.word_id == word_id,
                PracticeSession.member_id == member_id,
            )
        )
        today_cnt = (await self.session.execute(
            base.where(func.DATE(PracticeRecord.created_at) == today)
        )).scalar_one()
        prior_cnt = (await self.session.execute(
            base.where(func.DATE(PracticeRecord.created_at) < today)
        )).scalar_one()
        return today_cnt == 0, prior_cnt == 0

    async def _tick_daily_task(
        self, member_id: int, unit_id: int, today: date, is_new_word: bool,
    ) -> None:
        """找到包含该 unit 的 active plan 对应今日的 daily_task，给对应槽位 +1。

        - 新词 → completed_new+1（不超过 new_count）
        - 复习词 → completed_review+1（不超过 review_count）
        - 两个槽位都到顶 → status 置 completed
        - 没有匹配的 plan/task → 静默返回
        """
        stmt = (
            select(DailyTask)
            .join(LearningPlan, LearningPlan.id == DailyTask.plan_id)
            .join(PlanUnit, PlanUnit.plan_id == LearningPlan.id)
            .where(
                LearningPlan.member_id == member_id,
                LearningPlan.status == PlanStatus.active,
                PlanUnit.unit_id == unit_id,
                DailyTask.task_date == today,
                DailyTask.status != TaskStatus.completed,
            )
            .limit(1)
        )
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if task is None:
            return

        if is_new_word:
            if task.completed_new < task.new_count:
                task.completed_new += 1
        else:
            if task.completed_review < task.review_count:
                task.completed_review += 1

        if task.completed_new >= task.new_count and task.completed_review >= task.review_count:
            task.status = TaskStatus.completed
