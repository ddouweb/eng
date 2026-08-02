import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gamification import MAX_FREEZE_BALANCE, STREAK_BADGE_THRESHOLDS, XP_BADGE_THRESHOLDS, difficulty_mult
from app.srs import update_srs
from app.models.enums import MasteryLevel, PlanStatus, PracticeMode, TagType, TaskStatus, TaskType
from app.models.mastery import MasteryRecord
from app.models.member import Member
from app.models.plan import DailyTask, LearningPlan, PlanUnit
from app.models.practice import PracticeRecord, PracticeSession
from app.models.streak import MemberBadge, MemberStreak
from app.models.word import Word, WordTag
from app.repositories.mastery_repo import MasteryRepo
from app.repositories.practice_repo import PracticeRecordRepo, PracticeSessionRepo
from app.repositories.wrong_book_repo import WrongWordBookRepo
from app.schemas.common import success
from app.schemas.exceptions import AppException
from app.utils.weighting import compute_weight, weighted_sample
from app.utils.phonetics import phonetic

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
        include_mastered: bool = False,
    ) -> dict:
        questions = await self._build_questions(
            member_id, unit_ids, count, task_type=task_type,
            include_mastered=include_mastered,
        )
        if not questions:
            if task_type == TaskType.weekly_review:
                raise AppException(400, "暂无到期复习词（周）")
            elif task_type == TaskType.monthly_review:
                raise AppException(400, "暂无到期复习词（月）")
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

        # 坚持机制：streak / XP / 徽章（同事务更新，失败随业务一起回滚）
        gamified = await self._apply_gamification(
            ps.member_id, is_correct, is_new_word, mastery,
        )

        await self.session.commit()

        return success(data={
            "is_correct": is_correct,
            "correct_answer": word.english,
            "mastery": self._mastery_dict(mastery),
            "streak": gamified["streak"],
            "xp_delta": gamified["xp_delta"],
            "total_xp": gamified["total_xp"],
            "new_badges": gamified["new_badges"],
        })

    async def finish_practice(self, session_id: int) -> dict:
        ps = await self.session_repo.get_by_id(session_id)
        if not ps:
            raise AppException(404, "Practice session not found")
        if ps.ended_at:
            raise AppException(400, "Session already ended")

        ps.ended_at = datetime.now()
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

    async def rejudge_answer(
        self, session_id: int, word_id: int, is_correct: bool,
    ) -> dict:
        """结束页改判某题正误（人工覆盖）。绕过 submit 的 ended_at 拒绝、幂等去重
        与客观题服务端复判，按目标值覆盖更新 record / 会话计数 / mastery / SRS /
        错题本 / 每日任务 / XP。徽章正向补发、不回收。

        - 幂等：record 已是目标态 → changed=False，不重复加减。
        - 下溢保护：所有减法用 max(0, ...) 兜底。
        - SRS 近似：wrong→correct 时历史 prev_interval 已丢失，按当前 ease 回补 +
          新 consecutive_correct 重算 interval（接受近似），详见 srs.update_srs。
        """
        ps = await self.session_repo.get_by_id(session_id)
        if not ps:
            raise AppException(404, "Practice session not found")
        # 不检查 ended_at —— 改判正发生在结束页（会话已 finish）
        qset = ps.question_word_ids
        if isinstance(qset, list) and qset and word_id not in qset:
            raise AppException(400, "该单词不在本次练习题集中")

        word = await self.session.get(Word, word_id)
        if not word:
            raise AppException(404, "Word not found")

        # FOR UPDATE 行锁读取唯一 record，防并发改判撞车
        record = await self.record_repo.get_by_session_word_for_update(session_id, word_id)
        if record is None:
            raise AppException(404, "该题尚未作答，无法改判")

        # 幂等：已是目标态 → 不重复加减
        if record.is_correct == is_correct:
            mastery = await self.mastery_repo.get_by_member_word(ps.member_id, word_id)
            return success(data={
                "is_correct": is_correct, "changed": False,
                "correct_count": ps.correct_count, "accuracy": self._accuracy(ps),
                "mastery": self._mastery_dict(mastery),
            })

        record.is_correct = is_correct  # 人工覆盖，不走 _server_judge
        today = date.today()

        # ── 计数逆向 + SRS 重算 ──
        mastery = await self.mastery_repo.get_or_create(ps.member_id, word_id)
        if is_correct:
            # wrong → correct
            ps.correct_count += 1
            mastery.correct_count += 1
            mastery.consecutive_correct += 1
            mastery.wrong_count = max(0, mastery.wrong_count - 1)
            update_srs(mastery, True, today)
            # 错题本回退：原 wrong 时 upsert 过 → wrong_count-1，到 0 则删除
            wb = await self.wb_repo.get_by_member_word(ps.member_id, word_id)
            if wb is not None:
                if wb.wrong_count > 1:
                    wb.wrong_count -= 1
                else:
                    await self.wb_repo.delete_by_member_word(ps.member_id, word_id)
        else:
            # correct → wrong
            ps.correct_count = max(0, ps.correct_count - 1)
            mastery.correct_count = max(0, mastery.correct_count - 1)
            mastery.wrong_count += 1
            mastery.consecutive_correct = 0
            update_srs(mastery, False, today)
            await self.wb_repo.upsert_on_wrong(ps.member_id, word_id)
        mastery.last_reviewed_at = datetime.now()
        await self.session.flush()

        # ── 每日任务：wrong→correct 补推进 review 槽；correct→wrong 回退 ──
        # _classify_attempt 按历史记录数判定 is_new_word，与 is_correct 无关，改判后稳定
        _, is_new_word = await self._classify_attempt(ps.member_id, word_id, today)
        if is_correct:
            await self._tick_daily_task(ps.member_id, word.unit_id, today, is_new_word=False)
        else:
            await self._untick_daily_task(ps.member_id, word.unit_id, today)

        # ── XP：wrong→correct 按当前难度系数补发（加法，不会过度）；
        #        correct→wrong 保持 flat 5/2 扣回——历史 XP 可能按 flat 发放，
        #        若按系数会过度扣回损伤用户（max(0) 防负）。不对称是有意为之 ──
        member = await self.session.get(Member, ps.member_id)
        xp_delta = 0
        if is_correct:
            xp_delta = round(2 * difficulty_mult(mastery))
            if member is not None:
                member.total_xp = (member.total_xp or 0) + xp_delta
        else:
            xp_delta = 5 if is_new_word else 2
            if member is not None:
                member.total_xp = max(0, (member.total_xp or 0) - xp_delta)
        await self.session.flush()

        # streak 跳过（天然幂等，今日首次提交时已推进）

        # 徽章：wrong→correct 可能升 permanent → first_permanent；correct→wrong 不回收
        new_badges: list[str] = []
        if is_correct and member is not None:
            state = await self._get_or_create_streak(ps.member_id)
            new_badges = await self._check_and_award_badges(
                ps.member_id, state, member, mastery,
            )

        await self.session.commit()

        return success(data={
            "is_correct": is_correct, "changed": True,
            "correct_count": ps.correct_count, "accuracy": self._accuracy(ps),
            "xp_delta": xp_delta,
            "total_xp": (member.total_xp if member else 0),
            "mastery": self._mastery_dict(mastery),
            "new_badges": new_badges,
        })

    @staticmethod
    def _accuracy(ps: PracticeSession) -> float:
        """复刻 finish_practice 的正确率口径：correct_count/total_count，钳制 [0,100]。"""
        if ps.total_count > 0:
            return round(min(100.0, ps.correct_count / ps.total_count * 100), 1)
        return 0.0

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
        include_mastered: bool = False,
    ) -> list[dict]:
        today = date.today()

        # 候选词范围：统一按 unit_ids + 虚拟错题本（weekly/monthly 不再用时间窗，
        # 改为范围内「到期优先」，见 _select_questions）。
        has_wrong_book = WRONG_BOOK_VIRTUAL_UNIT_ID in unit_ids
        real_unit_ids = [u for u in unit_ids if u != WRONG_BOOK_VIRTUAL_UNIT_ID]
        conditions = []
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

        # 构造候选：compute_weight 带 SM-2 到期因子；三轮错题刷限定 wrong_count>0 且非 permanent
        candidates = []
        for wid, (word, tags) in word_tags.items():
            mastery = mastery_map.get(wid)
            level = mastery.level if mastery else MasteryLevel.unlearned
            if task_type == TaskType.wrong_word_drill:
                if mastery is None or mastery.wrong_count <= 0 or level == MasteryLevel.permanent:
                    continue
            nrd = mastery.next_review_date if mastery else None
            is_due = nrd is not None and nrd <= today
            w = compute_weight(level, tags, nrd, today)
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
                    "is_due": is_due,
                    "is_new": mastery is None,
                    "overdue_days": (today - nrd).days if is_due else 0,
                    "wrong_count": mastery.wrong_count if mastery else 0,
                    # 富字段透传给前端：练习答错揭示时展示音标/词性/英释/例句
                    # phonetic 缺省时由 app.utils.phonetics 用 eng_to_ipa 现算回退
                    "phonetic": phonetic(word.english, word.phonetic),
                    "definition": word.definition,
                    "pos": word.pos,
                    "example": word.example,
                })

        if not candidates:
            return []
        return self._select_questions(candidates, count, task_type, include_mastered)

    @staticmethod
    def _select_questions(
        candidates: list[dict], count: int, task_type: TaskType | None,
        include_mastered: bool = False,
    ) -> list[dict]:
        """按模式选 count 题：到期优先（逾期多、错得多优先），新词/其他加权补量。

        - 到期池 due_all 含 permanent 的到期词（「永久掌握」到期也低频回炉，不再永不出现）。
        - weekly/monthly：到期队列，不足回填未到期 learning/familiar（排除新词，避免混入）。
        - wrong_word_drill：候选已筛 wrong_count>0，按 (overdue, wrong) 排序（仍排除 permanent）。
        - 普通/learn：到期优先 → 新词加权 → 未到期兜底，三桶互斥并按 chosen_ids 去重。
        - include_mastered=True（自由练习「全部」）：普通分支兜底池放开 permanent 未到期词。
        """
        def due_first(arr: list[dict]) -> list[dict]:
            return sorted(arr, key=lambda c: (-c["overdue_days"], -c["wrong_count"]))

        due_all = [c for c in candidates if c["is_due"]]
        non_perm = [c for c in candidates if c["mastery_level"] != "permanent"]

        if task_type in (TaskType.weekly_review, TaskType.monthly_review):
            chosen = due_first(due_all)[:count]
            if len(chosen) < count:
                chosen_ids = {x["word_id"] for x in chosen}
                rest = [c for c in non_perm if c["word_id"] not in chosen_ids and not c["is_new"]]
                chosen += weighted_sample(rest, count - len(chosen))
            return chosen[:count]

        if task_type == TaskType.wrong_word_drill:
            return due_first(non_perm)[:count]

        # 普通 / learn
        chosen = due_first(due_all)[:count]
        if len(chosen) < count:
            chosen_ids = {x["word_id"] for x in chosen}
            new = [c for c in candidates if c["is_new"] and c["word_id"] not in chosen_ids]
            chosen += weighted_sample(new, count - len(chosen))
        if len(chosen) < count:
            chosen_ids = {x["word_id"] for x in chosen}
            # include_mastered（自由练习「全部」）：兜底池放开 permanent 未到期词，
            # 由 weighting 的 0.3 权重低频采样；常规练习仍用 non_perm 排除已掌握词。
            pool = candidates if include_mastered else non_perm
            other = [c for c in pool if not c["is_due"] and not c["is_new"]
                     and c["word_id"] not in chosen_ids]
            chosen += weighted_sample(other, count - len(chosen))
        return chosen[:count]

    async def _generate_options(self, correct: dict, all_questions: list[dict]) -> list[str]:
        """英→中选择题选项：正确答案 + 3 个来自 session 其它题的中文干扰项。

        干扰项按归一化文本去重，并排除与正确答案同义的项（词库常见多词同译，
        如 hi/hello→你好；否则会出现两个一模一样的正确选项）。归一化口径与
        _server_judge 复判一致（_normalize），保证「出题去重」与「服务端判分」
        对"同义"的判定不分歧。
        """
        answer = correct["chinese"]
        seen: set[str] = {self._normalize(answer)} if answer else set()
        deduped: list[str] = []
        for q in all_questions:
            if q["word_id"] == correct["word_id"]:
                continue
            c = q["chinese"]
            if not c:
                continue
            key = self._normalize(c)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(c)
        wrong = random.sample(deduped, min(3, len(deduped)))
        while len(wrong) < 3:  # 词库太小才占位补齐；占位不进采样池，避免占位重复
            wrong.append("(无选项)")
        options = wrong + [answer]
        random.shuffle(options)
        return options

    @staticmethod
    def _normalize(s: str) -> str:
        """小写 + 仅保留字母数字（汉字属字母会被保留），忽略大小写/空格/标点差异。
        供客观题服务端复判（_server_judge）与选择题选项去重（_generate_options）共用，
        确保两者对"同义/同形"的判定口径一致。"""
        return "".join(ch for ch in s.lower() if ch.isalnum())

    @staticmethod
    def _server_judge(
        mode: PracticeMode, word: Word, user_answer: str | None, client_correct: bool,
    ) -> bool:
        """客观题服务端复判：忽略客户端 is_correct，按答案重新判定。

        - 英文输出型（拼写/听写/重排/中→英选择）：答案应等于 word.english
        - 中文输出型（英→中默写/选择/限时挑战）：答案应等于 word.chinese
        - 主观型（闪卡/记忆/连线/对话等）：无客观答案，回退客户端判定
        缺少 user_answer 时也无法复判，回退客户端（避免误判为错）。
        """
        en_modes = {
            PracticeMode.spelling, PracticeMode.dictation,
            PracticeMode.scramble, PracticeMode.cn2en_choice,
        }
        # timed_challenge 与 choice 同构（给英文选中文释义，答案=word.chinese），
        # 纳入服务端复判以防伪造 is_correct 刷 XP/掌握度。
        cn_modes = {PracticeMode.choice, PracticeMode.en2cn_write, PracticeMode.timed_challenge}
        if mode in en_modes:
            target = word.english
        elif mode in cn_modes:
            target = word.chinese
        else:
            return client_correct
        if not user_answer or target is None:
            return client_correct

        return PracticeService._normalize(user_answer) == PracticeService._normalize(target)

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
        today = date.today()

        if is_correct:
            record.correct_count += 1
            record.consecutive_correct += 1
        else:
            record.wrong_count += 1
        # SM-2 间隔重复：原地更新 interval/ease/next_review_date/level（答错时 cc 归 0）
        update_srs(record, is_correct, today)
        record.last_reviewed_at = datetime.now()

        await self.session.flush()
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

        # review_count 保持 plan 建表时的静态槽位（不在此动态覆盖）。due-first 在选词层
        # _build_questions 生效（出题优先到期词），与 task 完成判定解耦：曾尝试用 member 全量
        # due 膨胀 review_count，会在多 plan / 存在 plan 外到期词时让任务永远完不成（且手动
        # update_task 也被堵），已回退为静态槽位。
        #
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

    async def _untick_daily_task(
        self, member_id: int, unit_id: int, today: date,
    ) -> None:
        """rejudge 从对改错时回退今日任务槽位（与 _tick_daily_task 对称）。

        - review 槽 -1（max 0 兜底）；learn 的 new 槽不改（改判不改变 new/review 归类）。
        - 回退后若槽位未满，把 status 从 completed 退回 in_progress。
        - 不带 status != completed 过滤：需触达已 completed 的任务来回退。
        - 盲区：无法精确得知原 correct 提交是否真 tick 过（is_first_today 已不可重建），
          按「假设 tick 过」回退；最坏 completed_review 多减 1（下限 0），状态机不卡死。
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
            )
        )
        tasks = (await self.session.execute(stmt)).scalars().all()
        for task in tasks:
            if task.completed_review > 0:
                task.completed_review -= 1
            if (
                task.status == TaskStatus.completed
                and (task.completed_new < task.new_count
                     or task.completed_review < task.review_count)
            ):
                task.status = TaskStatus.in_progress

    # ─────────────────────────────────────────────────────
    # 坚持机制（streak / freeze / XP / 徽章）
    # ─────────────────────────────────────────────────────
    async def _apply_gamification(
        self, member_id: int, is_correct: bool, is_new_word: bool,
        mastery: MasteryRecord | None,
    ) -> dict:
        """每次提交后更新 XP / streak / 徽章，返回快照供前端即时反馈。

        - XP：每次答对累加（新词 5 / 复习 2 × 难度系数，见 gamification.difficulty_mult）。
        - streak：仅「今天首次该成员练习」推进一次（由 last_active_date 判定，天然幂等）；
          断签时优先消耗 freeze 把缺口补上，补不满才重置为 1。
        - 徽章：达阈值即发放（幂等，uq_member_badge 兜底）。
        """
        member = await self.session.get(Member, member_id)
        state = await self._get_or_create_streak(member_id)
        today = date.today()

        # 1) XP：基础（新词 5 / 复习 2）× 难度系数（见 gamification.difficulty_mult）
        xp_delta = 0
        if is_correct and member is not None:
            xp_delta = round((5 if is_new_word else 2) * difficulty_mult(mastery))
            member.total_xp = (member.total_xp or 0) + xp_delta

        # 2) 月度 freeze 补充（跨月首次访问 +1，上限 MAX_FREEZE_BALANCE）
        self._maybe_grant_monthly_freeze(state, today)

        # 3) streak 推进（纯计算抽到 _advance_streak，便于单测）
        self._advance_streak(state, today)

        await self.session.flush()

        # 4) 徽章
        new_badges = await self._check_and_award_badges(member_id, state, member, mastery)

        return {
            "streak": self._streak_dict(state),
            "xp_delta": xp_delta,
            "total_xp": (member.total_xp if member else 0),
            "new_badges": new_badges,
        }

    async def _get_or_create_streak(self, member_id: int) -> MemberStreak:
        state = await self.session.get(MemberStreak, member_id)
        if state is None:
            state = MemberStreak(member_id=member_id)
            self.session.add(state)
            await self.session.flush()
        return state

    @staticmethod
    def _maybe_grant_monthly_freeze(state: MemberStreak, today: date) -> None:
        """每月首次访问补 1 个 freeze（上限 MAX_FREEZE_BALANCE）；首月只登记不补。"""
        month = today.strftime("%Y-%m")
        if state.freeze_grant_month == month:
            return
        if state.freeze_grant_month is not None:
            state.freeze_balance = min(state.freeze_balance + 1, MAX_FREEZE_BALANCE)
        state.freeze_grant_month = month

    @staticmethod
    def _advance_streak(state: MemberStreak, today: date) -> None:
        """推进一次连续天数（调用方保证仅在「今天首次」调用），原地修改 state。

        - 上次活跃 == 今天：保持不变（幂等）。
        - 首次（last 为空）：current = 1。
        - 否则：中间缺失天数 gap = (today - last).days - 1；用 freeze 优先补 gap，
          补满则 streak 接续 +1，补不满则重置为 1（freeze 是稀缺资源，只补最近缺口）。
        """
        if state.last_active_date == today:
            return
        if state.last_active_date is None:
            state.current_streak = 1
        else:
            gap = (today - state.last_active_date).days - 1
            if gap > 0:
                used = min(gap, state.freeze_balance)
                state.freeze_balance -= used
                gap -= used
            state.current_streak = state.current_streak + 1 if gap <= 0 else 1
        state.last_active_date = today
        if state.current_streak > state.longest_streak:
            state.longest_streak = state.current_streak

    async def _check_and_award_badges(
        self, member_id: int, state: MemberStreak,
        member: Member | None, mastery: MasteryRecord | None,
    ) -> list[str]:
        xp = member.total_xp if member else 0
        candidates: list[str] = []
        for days, key in STREAK_BADGE_THRESHOLDS:
            if state.current_streak >= days:
                candidates.append(key)
        for x, key in XP_BADGE_THRESHOLDS:
            if xp >= x:
                candidates.append(key)
        # first_permanent：该词刚升到 permanent，且该 member 此前（含本次）只有 ≤1 条 permanent
        if mastery is not None and mastery.level == MasteryLevel.permanent:
            cnt = await self.session.scalar(
                select(func.count()).select_from(MasteryRecord).where(
                    MasteryRecord.member_id == member_id,
                    MasteryRecord.level == MasteryLevel.permanent,
                )
            )
            if cnt is not None and cnt <= 1:
                candidates.append("first_permanent")

        new_badges: list[str] = []
        for key in candidates:
            if await self._award_badge_if_new(member_id, key):
                new_badges.append(key)
        return new_badges

    async def _award_badge_if_new(self, member_id: int, key: str) -> bool:
        existing = await self.session.scalar(
            select(MemberBadge).where(
                MemberBadge.member_id == member_id, MemberBadge.badge_key == key,
            )
        )
        if existing:
            return False
        self.session.add(MemberBadge(member_id=member_id, badge_key=key))
        await self.session.flush()
        return True

    @staticmethod
    def _streak_dict(state: MemberStreak) -> dict:
        return {
            "current_streak": state.current_streak,
            "longest_streak": state.longest_streak,
            "freeze_balance": state.freeze_balance,
            "last_active_date": (
                state.last_active_date.isoformat() if state.last_active_date else None
            ),
        }
