import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, PracticeMode, TagType
from app.models.mastery import MasteryRecord
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
