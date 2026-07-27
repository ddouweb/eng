"""rejudge_answer（结束页改判）单元测试。

聚焦核心计数/XP/幂等/下溢/边界分支；内部辅助方法（_classify_attempt /
_tick/_untick_daily_task / _get_or_create_streak / _check_and_award_badges /
_mastery_dict）mock 掉以隔离逻辑，_accuracy 让其真实跑（ps 提供整型字段）。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import PracticeMode
from app.schemas.exceptions import AppException
from app.services.practice_service import PracticeService


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def service(mock_session):
    return PracticeService(mock_session)


def _setup_rejudge(
    service, *, record_is_correct, ps_correct_count=3, ps_ended=True,
    mastery_correct=1, mastery_wrong=1, mastery_consec=0,
    mastery_ease=2.5, mastery_level="learning",
    member_xp=10, word_id=42, qset=None, is_new_word=False,
):
    """统一构造 rejudge 的 mock 上下文，返回 (ps, record, mastery, member) 供断言。"""
    ps = MagicMock(
        id=1, member_id=7,
        ended_at="2026-01-01T00:00:00" if ps_ended else None,
        correct_count=ps_correct_count, total_count=10,
        question_word_ids=qset if qset is not None else [42],
    )
    record = MagicMock(is_correct=record_is_correct)
    mastery = MagicMock(
        correct_count=mastery_correct, wrong_count=mastery_wrong,
        consecutive_correct=mastery_consec,
        ease_factor=mastery_ease, level=mastery_level,
    )
    member = MagicMock(total_xp=member_xp)
    word = MagicMock(id=word_id, unit_id=10, english="hello", chinese="你好")

    service.session_repo.get_by_id = AsyncMock(return_value=ps)
    service.record_repo.get_by_session_word_for_update = AsyncMock(return_value=record)
    service.session.get = AsyncMock(
        side_effect=lambda cls, _mid: word if cls.__name__ == "Word" else member
    )
    service.mastery_repo.get_or_create = AsyncMock(return_value=mastery)
    service.mastery_repo.get_by_member_word = AsyncMock(return_value=mastery)
    service.wb_repo.get_by_member_word = AsyncMock(return_value=MagicMock(wrong_count=mastery_wrong))
    service.wb_repo.delete_by_member_word = AsyncMock()
    service.wb_repo.upsert_on_wrong = AsyncMock()
    service._classify_attempt = AsyncMock(return_value=(False, is_new_word))
    service._tick_daily_task = AsyncMock()
    service._untick_daily_task = AsyncMock()
    service._get_or_create_streak = AsyncMock(return_value=MagicMock())
    service._check_and_award_badges = AsyncMock(return_value=[])
    service._mastery_dict = MagicMock(return_value={"level": "learning"})
    service.session.flush = AsyncMock()
    service.session.commit = AsyncMock()
    return ps, record, mastery, member, word


@pytest.mark.asyncio
async def test_rejudge_wrong_to_correct(service):
    ps, record, mastery, member, _ = _setup_rejudge(
        service, record_is_correct=False, mastery_wrong=1,
    )

    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=True)

    assert result["code"] == 200
    assert result["data"]["changed"] is True
    assert record.is_correct is True
    assert ps.correct_count == 4              # 3 + 1
    assert mastery.correct_count == 2         # 1 + 1
    assert mastery.consecutive_correct == 1   # 0 + 1
    assert mastery.wrong_count == 0           # max(0, 1-1)
    service.wb_repo.delete_by_member_word.assert_awaited_once()  # wrong_count 1→0 删除
    service.wb_repo.upsert_on_wrong.assert_not_awaited()
    service._tick_daily_task.assert_awaited_once()
    service._untick_daily_task.assert_not_awaited()
    # 补发按难度系数：mastery 经 update_srs 后 ease≈2.6 / level=learning / wrong=0
    # → difficulty_mult=1.3 → round(2*1.3)=round(2.6)=3
    assert result["data"]["xp_delta"] == 3
    assert member.total_xp == 13              # 10 + 3


@pytest.mark.asyncio
async def test_rejudge_correct_to_wrong(service):
    ps, record, mastery, member, _ = _setup_rejudge(
        service, record_is_correct=True, mastery_correct=2, mastery_wrong=0, mastery_consec=3,
    )

    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=False)

    assert result["code"] == 200
    assert result["data"]["changed"] is True
    assert record.is_correct is False
    assert ps.correct_count == 2              # max(0, 3-1)
    assert mastery.correct_count == 1         # max(0, 2-1)
    assert mastery.wrong_count == 1           # 0 + 1
    assert mastery.consecutive_correct == 0   # 归零
    service.wb_repo.upsert_on_wrong.assert_awaited_once()
    service._untick_daily_task.assert_awaited_once()
    service._tick_daily_task.assert_not_awaited()
    assert result["data"]["xp_delta"] == 2    # is_new_word=False → 精确扣 2
    assert member.total_xp == 8               # max(0, 10-2)


@pytest.mark.asyncio
async def test_rejudge_correct_to_wrong_new_word_claws_back_5(service):
    """correct→wrong 且该词是新词 → 扣回 5（新词答对的 +5）。"""
    _ps, _r, _m, member, _ = _setup_rejudge(
        service, record_is_correct=True, is_new_word=True,
    )

    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=False)

    assert result["data"]["xp_delta"] == 5
    assert member.total_xp == 5               # max(0, 10-5)


@pytest.mark.asyncio
async def test_rejudge_correct_to_wrong_no_overclaw(service):
    """correct→wrong 扣回保持 flat 5/2——即便 mastery 很难(high mult)也不乘系数。

    防 over-claw：历史 XP 可能按 flat 发放，若按当前难度系数扣回会过度损伤用户。
    此处 mastery 极难（wrong=3/ease=1.3 → mult≈2.0），若误乘会扣 round(2*2.0)=4，
    但正确实现仍 flat 扣 2。
    """
    _ps, _r, _m, member, _ = _setup_rejudge(
        service, record_is_correct=True, is_new_word=False,
        mastery_wrong=3, mastery_ease=1.3, mastery_level="learning",
    )

    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=False)

    assert result["data"]["xp_delta"] == 2    # flat 扣回，不乘难度系数
    assert member.total_xp == 8               # max(0, 10-2)


@pytest.mark.asyncio
async def test_rejudge_idempotent_when_already_target(service):
    """record 已是目标态 → changed=False，不重复加减。"""
    _setup_rejudge(service, record_is_correct=True)

    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=True)

    assert result["code"] == 200
    assert result["data"]["changed"] is False
    service._tick_daily_task.assert_not_awaited()
    service._untick_daily_task.assert_not_awaited()
    service.wb_repo.delete_by_member_word.assert_not_awaited()
    service.wb_repo.upsert_on_wrong.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejudge_bypass_ended_at(service):
    """会话已结束（ended_at 非空）仍可改判 —— 与 submit 的 ended_at 拒绝不同。"""
    _setup_rejudge(service, record_is_correct=False, ps_ended=True)
    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=True)
    assert result["code"] == 200


@pytest.mark.asyncio
async def test_rejudge_underflow_wrong_count_clamped(service):
    """脏数据 mastery.wrong_count=0 时 wrong→correct：max(0,-1)=0 不崩，错题本删除。"""
    _setup_rejudge(service, record_is_correct=False, mastery_wrong=0)

    result = await service.rejudge_answer(session_id=1, word_id=42, is_correct=True)

    assert result["code"] == 200
    service.wb_repo.delete_by_member_word.assert_awaited_once()


@pytest.mark.asyncio
async def test_rejudge_word_not_in_qset_rejected(service):
    """改判词不在题集 → 400（防改判任意词）。"""
    _setup_rejudge(service, record_is_correct=False, qset=[100, 101])

    with pytest.raises(AppException) as exc_info:
        await service.rejudge_answer(session_id=1, word_id=42, is_correct=True)
    assert exc_info.value.code == 400


@pytest.mark.asyncio
async def test_rejudge_record_not_found(service):
    """该题尚未作答（无 record）→ 404，不能改判。"""
    ps = MagicMock(
        id=1, member_id=7, ended_at=None, correct_count=3, total_count=10,
        question_word_ids=[42],
    )
    service.session_repo.get_by_id = AsyncMock(return_value=ps)
    service.record_repo.get_by_session_word_for_update = AsyncMock(return_value=None)

    with pytest.raises(AppException) as exc_info:
        await service.rejudge_answer(session_id=1, word_id=42, is_correct=True)
    assert exc_info.value.code == 404


def test_server_judge_timed_challenge_in_cn_modes():
    """timed_challenge 纳入 cn_modes：按 word.chinese 服务端复判，防伪造 is_correct。"""
    word = MagicMock(english="hello", chinese="你好")
    # 选对中文 → True（即便客户端传 False）
    assert PracticeService._server_judge(
        PracticeMode.timed_challenge, word, "你好", False,
    ) is True
    # 选错中文 → False（即便客户端传 True）
    assert PracticeService._server_judge(
        PracticeMode.timed_challenge, word, "再见", True,
    ) is False
