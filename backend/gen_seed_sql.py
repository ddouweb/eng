#!/usr/bin/env python3
"""解析 18章答案.md 词汇表，生成初始化 SQL（unit + word，含 seq 序号）。

适配表结构（见迁移 001_phase1 / 006_word_seq）:
  unit(id, title, sequence[UNIQUE], created_at, updated_at)
  word(id, unit_id, english, chinese, type[默认 'word'], seq, created_at, updated_at)
  word.unit_id 外键 ON DELETE CASCADE

用法:
  python gen_seed_sql.py                       # 默认读 ../18章答案.md，写 ./seed_18_units.sql
  python gen_seed_sql.py 输入.md 输出.sql

特性:
  - 幂等: 开头 DELETE FROM unit WHERE title LIKE '18章答案 Unit%'；
          word 因 FK ON DELETE CASCADE 自动级联删除。
  - unit_id 关联: 每 unit 用 LAST_INSERT_ID() + 会话变量 @u。
  - 字符集: SET NAMES utf8mb4；单引号/反斜杠自动转义。
  - type 全部 'word'（文档无完整句子）；U13 NO21 印刷重复的两词各自保留。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

UNIT_TITLE_PREFIX = "18章答案 Unit"


def sql_escape(s: str) -> str:
    """转义 SQL 字符串字面量中的反斜杠与单引号。"""
    return s.replace("\\", "\\\\").replace("'", "''")


def parse_units(md_text: str) -> list[tuple[int, list[tuple[int, str, str]]]]:
    """从 markdown 提取 [(unit_no, [(seq, english, chinese), ...]), ...]。

    表格行: | seq | english | chinese |  （仅当 seq 为纯数字才采集）
    Unit 标题: ## Unit N  （遇到任意 ## 标题都会先结束当前 unit，避免误收"汇总"表）
    """
    units: list[tuple[int, list[tuple[int, str, str]]]] = []
    cur_no: int | None = None
    cur_words: list[tuple[int, str, str]] | None = None

    for line in md_text.splitlines():
        if re.match(r"^##\s+", line):  # 任意二级标题：先收尾当前 unit
            if cur_no is not None and cur_words is not None:
                units.append((cur_no, cur_words))
            cur_no, cur_words = None, None
            m = re.match(r"^##\s+Unit\s+(\d+)", line)
            if m:
                cur_no = int(m.group(1))
                cur_words = []
            continue
        if cur_no is None or cur_words is None or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].isdigit():
            cur_words.append((int(cells[0]), cells[1], cells[2]))
    if cur_no is not None and cur_words is not None:
        units.append((cur_no, cur_words))
    return units


def gen_sql(units: list[tuple[int, list[tuple[int, str, str]]]]) -> str:
    total = sum(len(w) for _, w in units)
    out: list[str] = [
        "-- ============================================================",
        f"-- {UNIT_TITLE_PREFIX} 词汇表初始化数据",
        f"-- 来源: 18章答案.md  (共 {len(units)} 个 Unit / {total} 词)",
        "-- 适配表: unit / word  (word.seq 见迁移 006_word_seq；word.unit_id ON DELETE CASCADE)",
        "-- 字符集: utf8mb4",
        "-- 幂等: 开头按 title 删除同名 unit；word 随外键级联删除，可安全重跑",
        "-- 注意: unit.sequence 唯一，若已被其它数据占用会冲突，请相应调整",
        "-- ============================================================",
        "",
        "SET NAMES utf8mb4;",
        "START TRANSACTION;",
        "",
        f"DELETE FROM unit WHERE title LIKE '{UNIT_TITLE_PREFIX}%';",
        "",
    ]
    for unit_no, words in units:
        title = f"{UNIT_TITLE_PREFIX} {unit_no}"
        out.append(f"-- ---------- Unit {unit_no}  ({len(words)} 词) ----------")
        out.append(
            f"INSERT INTO unit (title, sequence) VALUES ('{sql_escape(title)}', {unit_no});"
        )
        out.append("SET @u = LAST_INSERT_ID();")
        out.append("INSERT INTO word (unit_id, english, chinese, seq, type) VALUES")
        rows = [
            f"  (@u, '{sql_escape(en)}', '{sql_escape(cn)}', {seq}, 'word')"
            for seq, en, cn in words
        ]
        out.append(",\n".join(rows) + ";")
        out.append("")
    out.append("COMMIT;")
    out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve().parent
    md_path = Path(argv[1]) if len(argv) > 1 else here.parent / "18章答案.md"
    sql_path = Path(argv[2]) if len(argv) > 2 else here / "seed_18_units.sql"

    md_text = md_path.read_text(encoding="utf-8")
    units = parse_units(md_text)
    total = sum(len(w) for _, w in units)
    print(f"parsed: {len(units)} units, {total} words")
    for no, words in units:
        seqs = [s for s, _, _ in words]
        print(f"  Unit {no:>2}: {len(words):>3} words, seq {min(seqs)}..{max(seqs)}")
    sql = gen_sql(units)
    sql_path.write_text(sql, encoding="utf-8")
    print(f"wrote: {sql_path}  ({len(sql)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
