"""WordRepo.search 的语句构造测试（不连真实 DB）。

get_paginated 用 session.execute 执行两条语句（count、rows）。这里把 session.execute 模拟成
依次返回 count 结果与空行结果，捕获 count 语句编译后的 SQL，校验关键分支：未学习掌握度走
`NOT EXISTS`、其它等级走正向 `EXISTS`、member_id 进了子查询、标签 EXISTS、关键词 autoescape。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import MasteryLevel, TagType, WordType
from app.repositories.word_repo import WordRepo


def _norm(sql: str) -> str:
    return " ".join(sql.lower().split())


async def _run_search(**kwargs) -> str:
    session = MagicMock()
    total_exec = MagicMock()
    total_exec.scalar_one.return_value = 0
    rows_exec = MagicMock()
    rows_exec.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[total_exec, rows_exec])
    repo = WordRepo(session)
    await repo.search(**kwargs)
    total_stmt = session.execute.call_args_list[0].args[0]
    return _norm(str(total_stmt.compile(compile_kwargs={"literal_binds": True})))


@pytest.mark.asyncio
async def test_search_unlearned_filter_uses_not_exists_with_member():
    sql = await _run_search(level=MasteryLevel.unlearned, member_id=5)
    assert "not (exists" in sql                      # 未学习 -> 排除「存在非 unlearned 记录」
    assert "mastery_record.member_id = 5" in sql     # member_id 进了相关子查询
    assert "unlearned" in sql


@pytest.mark.asyncio
async def test_search_positive_level_filter_uses_plain_exists():
    sql = await _run_search(level=MasteryLevel.learning, member_id=9)
    assert "not (exists" not in sql                  # 非 unlearned -> 正向 EXISTS
    assert "exists (select" in sql
    assert "mastery_record.member_id = 9" in sql
    assert "learning" in sql


@pytest.mark.asyncio
async def test_search_no_level_no_mastery_clause():
    sql = await _run_search(q="apple", member_id=1)
    assert "mastery_record" not in sql


@pytest.mark.asyncio
async def test_search_tag_filter_exists():
    sql = await _run_search(tag=TagType.favorite)
    assert "word_tags" in sql and "favorite" in sql


@pytest.mark.asyncio
async def test_search_keyword_autoescape():
    # autoescape=True 会加 ESCAPE 子句；回归（去掉 autoescape）会让此断言失败。
    sql = await _run_search(q="50%")
    assert "like" in sql and "escape" in sql


@pytest.mark.asyncio
async def test_search_unit_and_type_filters():
    sql = await _run_search(unit_id=3, word_type=WordType.sentence)
    assert "unit_id = 3" in sql
    assert "'sentence'" in sql or "sentence" in sql
