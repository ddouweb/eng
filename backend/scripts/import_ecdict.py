"""
导入 ECDICT 考研(英语二)词汇到数据库，纳入日常训练闭环。

====================================================================
 数据来源（合法、开源、可商用）
====================================================================
ECDICT — https://github.com/skywind3000/ECDICT  (MIT/CC)
下载：Releases -> stardict.7z（解压得 stardict.csv）或 ecdict.db (SQLite)

====================================================================
 用法
====================================================================
    cd backend
    python scripts/import_ecdict.py --source /path/to/stardict.csv
    python scripts/import_ecdict.py --source /path/to/ecdict.db --dry-run

====================================================================
 导入规则
====================================================================
筛选: tag 含 'ky' (考研大纲词，约 5500)
分组（按 collins 词频星，拆成 3 个 Unit，便于 LearningPlan 分阶段背）:
    - 考研·高频核心   collins >= 4
    - 考研·常用       collins in (2, 3)
    - 考研·基础       collins <= 1 或缺失
标签:
    - 全部考研词                    -> exam_focus   (📚)
    - collins>=4 或 oxford=1        -> 额外 high_freq (🔥)
权重对接: weighting.py 已置 high_freq/exam_focus = 1.5，高频词练习自动优先
幂等: 按 (unit_id, english) 去重，可重复运行
"""
import argparse
import asyncio
import csv
import os
import sqlite3
import sys
from pathlib import Path

# 让脚本能 import app 包（支持 `python scripts/xxx.py` 直接运行）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Windows 控制台中文输出
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from sqlalchemy import select, func  # noqa: E402

from app.database import async_session_factory, engine  # noqa: E402
from app.models.enums import TagType, WordType  # noqa: E402
from app.models.unit import Unit  # noqa: E402
from app.models.word import Word, WordTag  # noqa: E402


# (Unit 标题, collins 分组谓词)
UNIT_DEFS = [
    ("考研·高频核心", lambda c: c is not None and c >= 4),
    ("考研·常用", lambda c: c is not None and 2 <= c <= 3),
    ("考研·基础", lambda c: c is None or c <= 1),
]

CHINESE_MAX_LEN = 500  # Word.chinese 字段长度上限
BATCH_SIZE = 500


def _parse_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _normalize(row: dict) -> dict:
    return {
        "word": (row.get("word") or "").strip(),
        "translation": (row.get("translation") or "").strip(),
        "collins": _parse_int(row.get("collins")),
        "oxford": _parse_int(row.get("oxford")),
    }


def load_ky_words(source: str) -> list[dict]:
    """读取 ECDICT 文件，返回考研词列表（已 _normalize）。"""
    ext = os.path.splitext(source)[1].lower()
    rows: list[dict] = []

    if ext == ".csv":
        with open(source, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if "ky" in (r.get("tag") or ""):
                    rows.append(_normalize(r))
    elif ext in (".db", ".sqlite", ".sqlite3"):
        conn = sqlite3.connect(source)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT word, translation, collins, oxford, tag "
            "FROM stardict WHERE tag LIKE '%ky%'"
        )
        for r in cur:
            rows.append(_normalize({
                "word": r["word"],
                "translation": r["translation"],
                "collins": r["collins"],
                "oxford": r["oxford"],
                "tag": r["tag"],
            }))
        conn.close()
    else:
        raise ValueError(f"不支持的文件格式: {ext}（请提供 .csv 或 .db）")

    return rows


def assign_unit(collins) -> str:
    for title, pred in UNIT_DEFS:
        if pred(collins):
            return title
    return UNIT_DEFS[-1][0]  # 兜底进基础组


def is_high_freq(row: dict) -> bool:
    return (row["collins"] is not None and row["collins"] >= 4) or row["oxford"] == 1


async def get_or_create_unit(session, title: str, sequence: int) -> Unit:
    stmt = select(Unit).where(Unit.title == title)
    unit = (await session.execute(stmt)).scalar_one_or_none()
    if unit:
        return unit
    unit = Unit(title=title, sequence=sequence)
    session.add(unit)
    await session.flush()
    return unit


async def run(source: str, dry_run: bool) -> None:
    print(f"读取 ECDICT: {source}")
    rows = [r for r in load_ky_words(source) if r["word"]]
    print(f"筛选出考研词 (ky): {len(rows)} 个")

    groups: dict[str, list] = {t: [] for t, _ in UNIT_DEFS}
    for r in rows:
        groups[assign_unit(r["collins"])].append(r)
    for t, _ in UNIT_DEFS:
        print(f"  · {t}: {len(groups[t])} 个")

    hf_total = sum(1 for r in rows if is_high_freq(r))
    print(f"  其中高频词 (将打 🔥): {hf_total} 个")

    if dry_run:
        print("\n[dry-run] 未写入数据库。去掉 --dry-run 执行实际导入。")
        return

    async with async_session_factory() as session:
        # Unit.sequence 接在现有最大值之后，避免唯一约束冲突
        max_seq = (await session.execute(
            select(func.coalesce(func.max(Unit.sequence), 0))
        )).scalar_one()
        base = max_seq + 1
        units: dict[str, Unit] = {}
        for idx, (title, _) in enumerate(UNIT_DEFS):
            units[title] = await get_or_create_unit(session, title, base + idx)
        await session.commit()

        total_created = total_skipped = total_hf = 0
        for title, _ in UNIT_DEFS:
            unit = units[title]
            pending = groups[title]
            if not pending:
                continue

            # 该 Unit 下已存在的 english（幂等去重）
            existing = {r[0] for r in (await session.execute(
                select(Word.english).where(Word.unit_id == unit.id)
            )).all()}

            seq = len(existing)
            to_create: list[Word] = []
            metas: list[bool] = []
            for r in pending:
                if r["word"] in existing:
                    total_skipped += 1
                    continue
                seq += 1
                cn = r["translation"][:CHINESE_MAX_LEN] or r["word"]
                to_create.append(Word(
                    unit_id=unit.id,
                    english=r["word"],
                    chinese=cn,
                    type=WordType.word,
                    seq=seq,
                ))
                metas.append(is_high_freq(r))

            # 分批写入，避免一次性 5500 条占用过大
            for i in range(0, len(to_create), BATCH_SIZE):
                bw = to_create[i:i + BATCH_SIZE]
                bm = metas[i:i + BATCH_SIZE]
                session.add_all(bw)
                await session.flush()  # 拿到自增 id

                tags: list[WordTag] = []
                for w, hf in zip(bw, bm):
                    tags.append(WordTag(word_id=w.id, tag=TagType.exam_focus))
                    if hf:
                        tags.append(WordTag(word_id=w.id, tag=TagType.high_freq))
                session.add_all(tags)
                await session.commit()
                for w in bw:
                    session.expunge(w)  # 释放内存

                total_created += len(bw)
                total_hf += sum(bm)
                print(f"  [{title}] 已写入 {len(bw)} 词 (高频 {sum(bm)})")

        print(
            f"\n完成: 新增 {total_created} 词, "
            f"跳过已存在 {total_skipped} 词, 高频标签 {total_hf} 个"
        )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 ECDICT 考研(英语二)词汇")
    parser.add_argument("--source", required=True, help="ECDICT 文件路径 (.csv 或 .db)")
    parser.add_argument("--dry-run", action="store_true", help="只预览分组，不写入数据库")
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"错误: 文件不存在 -> {args.source}")
        sys.exit(1)

    asyncio.run(run(args.source, args.dry_run))


if __name__ == "__main__":
    main()
