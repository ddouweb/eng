import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MasteryLevel, PlanStatus, PracticeMode, TagType, TaskStatus, TaskType
from app.models.mastery import MasteryRecord
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.practice import PracticeRecord, PracticeSession
from app.models.word import Word, WordTag
from app.repositories.mastery_repo import MasteryRepo
from app.repositories.practice_repo import PracticeRecordRepo, PracticeSessionRepo
from app.repositories.wrong_book_repo import WrongWordBookRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException
from app.utils.weighting import compute_weight, weighted_sample

# 错题本在前端以「虚拟 Unit」形式出现在 Unit 列表中，使用 0 作为虚拟 ID。
# 真实 Unit 表自增从 1 开始，0 不会冲突。start_practice 的 unit_ids 含 0 即表示
# 把该 member 的错题本词也加入候选池（可与真实 Unit 多选混合）。
WRONG_BOOK_VIRTUAL_UNIT_ID = 0


class PracticeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_repo = PracticeSessionRepo(session)
        self.record_repo = PracticeRecordRepo(session)
        self.mastery_repo = MasteryRepo(session)
        self.wb_repo = WrongWordBookRepo(session)

    async def start_practice(
        self, member_id: int, mode: PracticeMode,
        unit_ids: list[int], count: int = 10,
        task_type: TaskType | None = None,
    ) -> dict:
        questions = await self._build_questions(
            member_id, unit_ids, count, task_type=task_type,
        )
        if not questions:
            if task_type == TaskType.weekly_review:
                raise AppException(400, "本周暂无可复习词")
            elif task_type == TaskType.monthly_review:
                raise AppException(400, "本月暂无可复习词")
            elif task_type == TaskType.wrong_word_drill:
                raise AppException(400, "暂无错题可刷")
            raise AppException(400, "没有可练习的单词")

        ps = PracticeSession(
            member_id=member_id,
            mode=mode,
            total_count=len(questions),
            question_word_ids=[q["word_id"] for q in questions],
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

        # 题集归属校验：word_id 必须在本会话题集内（防提交任意词刷分）。
        # 旧会话 question_word_ids 为 NULL → 跳过（向后兼容）。
        qset = ps.question_word_ids
        if isinstance(qset, list) and qset and word_id not in qset:
            raise AppException(400, "该单词不在本次练习题集中")

        word = await self.session.get(Word, word_id)
        if not word:
            raise AppException(404, "Word not found")

        # 去重（幂等）：同一会话同一词只计一次。防止重复提交刷分，也容忍前端
        # rerun/重试导致的重复 _bg_submit —— 已有记录则直接回读，不重复计数/改掌握度。
        existing = await self.record_repo.get_by_session_word(session_id, word_id)
        if existing is not None:
            mastery = await self.mastery_repo.get_by_member_word(ps.member_id, word_id)
            return success(data={
                "is_correct": existing.is_correct,
                "correct_answer": word.english,
                "mastery": self._mastery_dict(mastery),
            })

        # 客观题服务端复判：忽略客户端传入的 is_correct，按答案重新判定，
        # 杜绝前端伪造 is_correct=true 刷分。主观题（闪卡/记忆/连线等）无客观答案，回退客户端。
        is_correct = self._server_judge(ps.mode, word, user_answer, is_correct)

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

        # 答错 → upsert 错题本（已有记录则 wrong_count +1，保留 added_at）
        # 答对时刻意不动错题本，需用户在错题本页手动移除
        if not is_correct:
            await self.wb_repo.upsert_on_wrong(
                member_id=ps.member_id,
                word_id=word_id,
            )

        # 答对 + 今天首次 → 回流到对应 active plan 的今日任务
        if is_correct and is_first_today:
            await self._tick_daily_task(ps.member_id, word.unit_id, today, is_new_word)

        await self.session.commit()

        return success(data={
            "is_correct": is_correct,
            "correct_answer": word.english,
            "mastery": self._mastery_dict(mastery),
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

        # 钳制正确率：去重后 correct_count ≤ total_count，理论上不会越界，
        # 但旧会话/异常数据下仍兜底，确保 accuracy ∈ [0, 100]。
        if ps.total_count > 0:
            accuracy = min(100.0, ps.correct_count / ps.total_count * 100)
        else:
            accuracy = 0.0

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

    async def _build_questions(
        self, member_id: int, unit_ids: list[int], count: int,
        task_type: TaskType | None = None,
    ) -> list[dict]:
        today = date.today()
        word_filter = None
        if task_type == TaskType.weekly_review:
            monday = today - timedelta(days=today.weekday())
            word_ids = await self.record_repo.get_word_ids_between(member_id, monday, today)
            if not word_ids:
                return []
            word_filter = Word.id.in_(word_ids)
        elif task_type == TaskType.monthly_review:
            month_start = today.replace(day=1)
            word_ids = await self.record_repo.get_word_ids_between(member_id, month_start, today)
            if not word_ids:
                return []
            word_filter = Word.id.in_(word_ids)
        elif task_type == TaskType.wrong_word_drill:
            # 三轮错题刷：候选限定为 unit 内、有错题记录且未到 permanent 的词
            word_filter = Word.unit_id.in_(unit_ids)
        else:
            # 普通模式：支持虚拟错题本单元（id=0）与真实 Unit 混合多选
            has_wrong_book = WRONG_BOOK_VIRTUAL_UNIT_ID in unit_ids
            real_unit_ids = [u for u in unit_ids if u != WRONG_BOOK_VIRTUAL_UNIT_ID]
            conditions = []
            wb_word_ids: list[int] = []
            if has_wrong_book:
                wb_word_ids = await self.wb_repo.list_word_ids_by_member(member_id)
                if wb_word_ids:
                    conditions.append(Word.id.in_(wb_word_ids))
            if real_unit_ids:
                conditions.append(Word.unit_id.in_(real_unit_ids))
            if not conditions:
                return []
            word_filter = conditions[0] if len(conditions) == 1 else or_(*conditions)

        stmt = (
            select(Word, WordTag.tag)
            .outerjoin(WordTag, WordTag.word_id == Word.id)
            .where(word_filter)
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

        # 三轮模式：在 mastery 维度做候选筛选
        if task_type == TaskType.wrong_word_drill:
            filtered = {
                wid: wt for wid, wt in word_tags.items()
                if (mastery_map.get(wid) is not None
                    and mastery_map[wid].wrong_count > 0
                    and mastery_map[wid].level != MasteryLevel.permanent)
            }
            if not filtered:
                return []
            word_tags = filtered

        candidates = []
        for wid, (word, tags) in word_tags.items():
            mastery = mastery_map.get(wid)
            level = mastery.level if mastery else MasteryLevel.unlearned
            w = compute_weight(level, tags)
            # 三轮加权：错得越多权重越高（每个 wrong_count +0.5 倍）
            if task_type == TaskType.wrong_word_drill and mastery:
                w *= (1.0 + mastery.wrong_count * 0.5)
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

    @staticmethod
    def _server_judge(
        mode: PracticeMode, word: Word, user_answer: str | None, client_correct: bool,
    ) -> bool:
        """客观题服务端复判：忽略客户端 is_correct，按答案重新判定。

        - 英文输出型（拼写/听写/重排/中→英选择）：答案应等于 word.english
        - 中文输出型（英→中默写/选择）：答案应等于 word.chinese
        - 主观型（闪卡/记忆/连线/对话等）：无客观答案，回退客户端判定
        缺少 user_answer 时也无法复判，回退客户端（避免误判为错）。
        """
        en_modes = {
            PracticeMode.spelling, PracticeMode.dictation,
            PracticeMode.scramble, PracticeMode.cn2en_choice,
        }
        cn_modes = {PracticeMode.choice, PracticeMode.en2cn_write}
        if mode in en_modes:
            target = word.english
        elif mode in cn_modes:
            target = word.chinese
        else:
            return client_correct
        if not user_answer or target is None:
            return client_correct

        def _norm(s: str) -> str:
            # 小写 + 仅保留字母数字（汉字属字母，会被保留），忽略大小写/空格/标点差异
            return "".join(ch for ch in s.lower() if ch.isalnum())

        return _norm(user_answer) == _norm(target)

    @staticmethod
    def _mastery_dict(mastery: MasteryRecord | None) -> dict:
        """统一掌握度快照序列化；mastery 为 None（从未练过）时给默认值。"""
        if mastery is None:
            return {
                "level": MasteryLevel.unlearned.value,
                "consecutive_correct": 0,
                "correct_count": 0,
                "wrong_count": 0,
            }
        return {
            "level": mastery.level.value,
            "consecutive_correct": mastery.consecutive_correct,
            "correct_count": mastery.correct_count,
            "wrong_count": mastery.wrong_count,
        }

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

        用一次条件聚合同时拿"今日次数"与"历史次数"（原先 2 次 COUNT 往返），
        并以 created_at 区间比较替代 func.DATE()，使其能命中 created_at 索引。
        """
        today_start = datetime.combine(today, time.min)
        tomorrow_start = today_start + timedelta(days=1)
        stmt = (
            select(
                func.coalesce(func.sum(case(
                    (and_(PracticeRecord.created_at >= today_start,
                          PracticeRecord.created_at < tomorrow_start), 1),
                    else_=0,
                )), 0),
                func.coalesce(func.sum(case(
                    (PracticeRecord.created_at < today_start, 1),
                    else_=0,
                )), 0),
            )
            .select_from(PracticeRecord)
            .join(PracticeSession, PracticeSession.id == PracticeRecord.session_id)
            .where(
                PracticeRecord.word_id == word_id,
                PracticeSession.member_id == member_id,
            )
        )
        row = (await self.session.execute(stmt)).one()
        today_cnt = int(row[0])
        prior_cnt = int(row[1])
        return today_cnt == 0, prior_cnt == 0

    async def _tick_daily_task(
        self, member_id: int, unit_id: int, today: date, is_new_word: bool,
    ) -> None:
        """找到包含该 unit 的 active plan 对应今日的 daily_task，给对应槽位 +1。

        - learn 类型：新词 → completed_new+1，复习词 → completed_review+1
        - weekly_review / monthly_review 类型：所有答对都 → completed_review+1（new_count=0）
        - 槽位到顶 → status 置 completed
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
        )
        tasks = (await self.session.execute(stmt)).scalars().all()
        if not tasks:
            return

        # 同一 unit 可能被多个 active plan 选中（如 forward + review_only），
        # 一次答对应推进所有匹配的当日任务，而非仅首个（原先 limit(1) 会漏推进）。
        for task in tasks:
            if task.task_type == TaskType.learn:
                slot = "new" if is_new_word else "review"
                if slot == "new" and task.completed_new < task.new_count:
                    task.completed_new += 1
                elif slot == "review" and task.completed_review < task.review_count:
                    task.completed_review += 1
            else:
                # weekly_review / monthly_review：只填 review 槽
                if task.completed_review < task.review_count:
                    task.completed_review += 1

            if task.completed_new >= task.new_count and task.completed_review >= task.review_count:
                task.status = TaskStatus.completed
