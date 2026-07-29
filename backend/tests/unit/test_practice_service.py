from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import MasteryLevel, PracticeMode, TaskStatus, TaskType
from app.schemas.exceptions import AppException
from app.services.practice_service import PracticeService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def service(mock_session):
    return PracticeService(mock_session)


def _make_word(word_id=1, english="hello", chinese="你好"):
    w = MagicMock(id=word_id, english=english, chinese=chinese)
    w.type.value = "word"
    return w


# _try_upgrade / _try_downgrade（计数式升降级）已由 SM-2 update_srs 替换，
# 相关算法测试见 tests/unit/test_srs.py（update_srs / interval_to_level）。


@pytest.mark.asyncio
async def test_submit_answer_session_not_found(service):
    service.session_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(AppException) as exc_info:
        await service.submit_answer(999, 1, True)
    assert exc_info.value.code == 404


@pytest.mark.asyncio
async def test_submit_answer_session_already_ended(service):
    ps = MagicMock(ended_at="2026-01-01")
    service.session_repo.get_by_id = AsyncMock(return_value=ps)
    with pytest.raises(AppException) as exc_info:
        await service.submit_answer(1, 1, True)
    assert exc_info.value.code == 400


@pytest.mark.asyncio
async def test_finish_practice(service, mock_session):
    ps = MagicMock(
        id=1, mode=PracticeMode.flashcard, total_count=10, correct_count=8,
        started_at=None, ended_at=None,
    )
    service.session_repo.get_by_id = AsyncMock(return_value=ps)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    result = await service.finish_practice(1)

    assert result["code"] == 200
    assert result["data"]["accuracy"] == 80.0
    assert ps.ended_at is not None


@pytest.mark.asyncio
async def test_finish_practice_not_found(service):
    service.session_repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(AppException) as exc_info:
        await service.finish_practice(999)
    assert exc_info.value.code == 404


# ────────────────────────────────────────────────────────────
# daily_task 回流测试
# ────────────────────────────────────────────────────────────


def _mock_classify_row(today_cnt: int, prior_cnt: int):
    """模拟 session.execute(...).one() 返回 (今日次数, 历史次数) 的链式调用。

    _classify_attempt 已改为一次条件聚合返回 (today_cnt, prior_cnt)。
    """
    result = MagicMock()
    result.one.return_value = (today_cnt, prior_cnt)
    return result


class TestClassifyAttempt:
    @pytest.mark.asyncio
    async def test_first_time_ever(self, service, mock_session):
        # 今天 0 条、历史 0 条 → (True, True)
        mock_session.execute = AsyncMock(return_value=_mock_classify_row(0, 0))
        is_first, is_new = await service._classify_attempt(1, 100, date(2026, 6, 16))
        assert is_first is True
        assert is_new is True

    @pytest.mark.asyncio
    async def test_already_practiced_today(self, service, mock_session):
        # 今天已有 1 条 → (False, True)
        mock_session.execute = AsyncMock(return_value=_mock_classify_row(1, 0))
        is_first, is_new = await service._classify_attempt(1, 100, date(2026, 6, 16))
        assert is_first is False
        assert is_new is True

    @pytest.mark.asyncio
    async def test_practiced_in_prior_days(self, service, mock_session):
        # 今天 0 条、历史 2 条 → (True, False)
        mock_session.execute = AsyncMock(return_value=_mock_classify_row(0, 2))
        is_first, is_new = await service._classify_attempt(1, 100, date(2026, 6, 16))
        assert is_first is True
        assert is_new is False


def _mock_task_result(task):
    """模拟 session.execute(...).scalars().all() 的链式调用。

    _tick_daily_task 已改为遍历所有匹配任务（去 limit(1)）；传 None 表示无匹配。
    """
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = [task] if task is not None else []
    result.scalars.return_value = scalars
    return result


class TestTickDailyTask:
    @pytest.mark.asyncio
    async def test_tick_new_word(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=3, completed_review=2,
            status=TaskStatus.in_progress,
            task_type=TaskType.learn,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=True)

        assert task.completed_new == 4
        assert task.completed_review == 2
        assert task.status == TaskStatus.in_progress

    @pytest.mark.asyncio
    async def test_tick_review_word(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=3, completed_review=2,
            status=TaskStatus.in_progress,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=False)

        assert task.completed_new == 3
        assert task.completed_review == 3
        assert task.status == TaskStatus.in_progress

    @pytest.mark.asyncio
    async def test_cap_new_does_not_overflow(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=10, completed_review=2,
            status=TaskStatus.in_progress,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=True)

        assert task.completed_new == 10  # 已满，不溢出

    @pytest.mark.asyncio
    async def test_both_filled_marks_completed(self, service, mock_session):
        task = MagicMock(
            new_count=10, review_count=5,
            completed_new=9, completed_review=5,
            status=TaskStatus.in_progress,
            task_type=TaskType.learn,
        )
        mock_session.execute = AsyncMock(return_value=_mock_task_result(task))

        await service._tick_daily_task(member_id=1, unit_id=1, today=date(2026, 6, 16), is_new_word=True)

        assert task.completed_new == 10
        assert task.completed_review == 5
        assert task.status == TaskStatus.completed

    @pytest.mark.asyncio
    async def test_no_matching_task_is_noop(self, service, mock_session):
        mock_session.execute = AsyncMock(return_value=_mock_task_result(None))

        # 不应抛异常
        await service._tick_daily_task(member_id=1, unit_id=999, today=date(2026, 6, 16), is_new_word=True)

    # 注：曾有的 test_review_count_inflated_to_member_due 已删除——动态膨胀 review_count 的
    # 方案会破坏 daily_task 完成闭环（见回归审查），已回退为静态 review_count 槽位。


@pytest.mark.asyncio
async def test_submit_answer_reflows_to_daily_task(service, mock_session):
    """完整链路：答对 + 首次今日 → 调 _tick_daily_task。"""
    ps = MagicMock(id=1, member_id=7, ended_at=None, correct_count=3)
    service.session_repo.get_by_id = AsyncMock(return_value=ps)

    word = MagicMock(id=42, unit_id=10, english="hello", chinese="你好")
    service.session.get = AsyncMock(return_value=word)

    service.record_repo.create = AsyncMock()
    service.record_repo.get_by_session_word = AsyncMock(return_value=None)  # 去重：无已有记录，走正常计分路径
    service._update_mastery = AsyncMock(return_value=MagicMock(
        level=MasteryLevel.learning, consecutive_correct=1,
        correct_count=1, wrong_count=0,
    ))
    mock_session.commit = AsyncMock()

    # _classify_attempt → (True, True) 首次今日 + 新词
    service._classify_attempt = AsyncMock(return_value=(True, True))
    service._tick_daily_task = AsyncMock()
    service._apply_gamification = AsyncMock(return_value={
        "streak": {}, "xp_delta": 0, "total_xp": 0, "new_badges": [],
    })

    result = await service.submit_answer(session_id=1, word_id=42, is_correct=True)

    assert result["code"] == 200
    service._tick_daily_task.assert_awaited_once()
    args, kwargs = service._tick_daily_task.call_args
    assert args == (7, 10, date.today(), True)


@pytest.mark.asyncio
async def test_submit_answer_wrong_answer_does_not_tick(service, mock_session):
    """答错不回流。"""
    ps = MagicMock(id=1, member_id=7, ended_at=None, correct_count=3)
    service.session_repo.get_by_id = AsyncMock(return_value=ps)

    word = MagicMock(id=42, unit_id=10, english="hello", chinese="你好")
    service.session.get = AsyncMock(return_value=word)

    service.record_repo.create = AsyncMock()
    service.record_repo.get_by_session_word = AsyncMock(return_value=None)  # 去重：无已有记录，走正常计分路径
    service._update_mastery = AsyncMock(return_value=MagicMock(
        level=MasteryLevel.unlearned, consecutive_correct=0,
        correct_count=0, wrong_count=1,
    ))
    mock_session.commit = AsyncMock()

    service._classify_attempt = AsyncMock(return_value=(True, True))
    service._tick_daily_task = AsyncMock()
    service.wb_repo.upsert_on_wrong = AsyncMock()  # 隔离错题本副作用
    service._apply_gamification = AsyncMock(return_value={
        "streak": {}, "xp_delta": 0, "total_xp": 0, "new_badges": [],
    })

    await service.submit_answer(session_id=1, word_id=42, is_correct=False)

    service._tick_daily_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_answer_second_attempt_today_does_not_tick(service, mock_session):
    """同一天二次答对：is_first_today=False → 不回流。"""
    ps = MagicMock(id=1, member_id=7, ended_at=None, correct_count=3)
    service.session_repo.get_by_id = AsyncMock(return_value=ps)

    word = MagicMock(id=42, unit_id=10, english="hello", chinese="你好")
    service.session.get = AsyncMock(return_value=word)

    service.record_repo.create = AsyncMock()
    service.record_repo.get_by_session_word = AsyncMock(return_value=None)  # 去重：无已有记录，走正常计分路径
    service._update_mastery = AsyncMock(return_value=MagicMock(
        level=MasteryLevel.learning, consecutive_correct=2,
        correct_count=2, wrong_count=0,
    ))
    mock_session.commit = AsyncMock()

    service._classify_attempt = AsyncMock(return_value=(False, False))  # 今天已练过
    service._tick_daily_task = AsyncMock()
    service._apply_gamification = AsyncMock(return_value={
        "streak": {}, "xp_delta": 0, "total_xp": 0, "new_badges": [],
    })

    await service.submit_answer(session_id=1, word_id=42, is_correct=True)

    service._tick_daily_task.assert_not_awaited()


# ────────────────────────────────────────────────────────────
# _select_questions（due-first 选词）
# ────────────────────────────────────────────────────────────


class TestSelectQuestions:
    def _c(self, wid, is_due=False, is_new=False, overdue=0, wrong=0, level="learning"):
        return {
            "word_id": wid, "weight": 1.0, "mastery_level": level,
            "is_due": is_due, "is_new": is_new, "overdue_days": overdue, "wrong_count": wrong,
        }

    def test_normal_due_first(self):
        cands = [self._c(1, is_due=True, overdue=3), self._c(2, is_new=True), self._c(3)]
        out = PracticeService._select_questions(cands, 2, None)
        ids = [c["word_id"] for c in out]
        assert 1 in ids            # 到期词必出
        assert len(out) == 2

    def test_weekly_uses_due_queue_with_backfill(self):
        cands = [self._c(1, is_due=True), self._c(2), self._c(3)]
        out = PracticeService._select_questions(cands, 3, TaskType.weekly_review)
        assert len(out) == 3       # due 不足时回填非到期词

    def test_wrong_drill_sorted_by_overdue_then_wrong(self):
        cands = [self._c(1, overdue=0, wrong=5), self._c(2, overdue=2, wrong=1)]
        out = PracticeService._select_questions(cands, 2, TaskType.wrong_word_drill)
        assert out[0]["word_id"] == 2   # overdue 多的在前

    def test_permanent_due_recycles(self):
        # 「永久掌握」到期也低频回炉（进到期池，不再永不出现）
        cands = [self._c(1, is_due=True, level="permanent", overdue=5)]
        out = PracticeService._select_questions(cands, 5, None)
        assert out and out[0]["word_id"] == 1

    def test_wrong_drill_excludes_permanent(self):
        # wrong_word_drill 仍排除 permanent（错题刷不碰永久词）
        cands = [self._c(1, is_due=True, level="permanent"), self._c(2, is_due=True)]
        out = PracticeService._select_questions(cands, 5, TaskType.wrong_word_drill)
        assert all(c["word_id"] != 1 for c in out)

    def test_normal_no_duplicate_word_ids(self):
        # due+新词 < count 触发兜底时，三桶间不得重复同一 word_id
        cands = [
            self._c(1, is_due=True),
            self._c(2, is_new=True), self._c(3, is_new=True),
            self._c(4), self._c(5),   # 未到期 learning 兜底
        ]
        out = PracticeService._select_questions(cands, 5, None)
        ids = [c["word_id"] for c in out]
        assert len(ids) == len(set(ids))   # 无重复


# ────────────────────────────────────────────────────────────
# _generate_options（英→中选项去重：防"两个相同正确答案"回归）
# ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_options_no_duplicate_correct_for_synonyms(service):
    """多词同译（hi/hello→你好）时，正确答案在选项中只出现一次。

    回归用例：词库存在多个英文词共享同一中文释义，旧实现把其它题的同义
    中文当作干扰项，导致选项里出现两个一模一样的"正确答案"。
    """
    correct = {"word_id": 1, "chinese": "你好"}
    others = [
        {"word_id": 2, "chinese": "你好"},     # 与正确答案同义 → 排除
        {"word_id": 3, "chinese": "谢谢"},
        {"word_id": 4, "chinese": "再见"},
        {"word_id": 5, "chinese": "你好。"},   # 归一化(去标点)后同义 → 同样排除
    ]
    options = await service._generate_options(correct, others)
    assert options.count("你好") == 1           # 核心：正确答案唯一（旧 bug 会重复）
    assert len(options) == 4
    assert "你好。" not in options               # 归一化同义项不作为独立干扰项


@pytest.mark.asyncio
async def test_generate_options_dedup_between_distractors(service):
    """干扰项之间也按归一化去重（多个其它题中文相同时只取一个）。"""
    correct = {"word_id": 1, "chinese": "苹果"}
    others = [
        {"word_id": 2, "chinese": "香蕉"},
        {"word_id": 3, "chinese": "香蕉"},      # 与 word_id=2 重复 → 去重
        {"word_id": 4, "chinese": "橘子"},
        {"word_id": 5, "chinese": "葡萄"},
    ]
    options = await service._generate_options(correct, others)
    assert len(options) == len(set(options))    # 选项整体无重复
    assert options.count("苹果") == 1


@pytest.mark.asyncio
async def test_generate_options_few_candidates_pads_placeholder(service):
    """词库太小（干扰项 < 3）时用占位补齐，不报错、正确答案仍唯一。"""
    correct = {"word_id": 1, "chinese": "苹果"}
    others = [{"word_id": 2, "chinese": "香蕉"}]   # 仅 1 个可用干扰项
    options = await service._generate_options(correct, others)
    assert options.count("苹果") == 1
    assert "香蕉" in options
    assert len(options) == 4
