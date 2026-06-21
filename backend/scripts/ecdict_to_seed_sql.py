"""
把 ECDICT 中的考研(英语二)大纲词导出成幂等 SQL 种子文件。

====================================================================
 数据来源（合法、开源、可商用）
====================================================================
ECDICT — https://github.com/skywind3000/ECDICT  (MIT/CC)
下载：Releases → ecdict-sqlite-28.zip → 解压得 stardict.db

====================================================================
 用法
====================================================================
    cd backend
    # 先下载 stardict.db 放到 ./data/stardict.db
    python scripts/ecdict_to_seed_sql.py --source ./data/stardict.db
    # → 生成 backend/seed_kaoyan_english2.sql

    # 自定义输出路径
    python scripts/ecdict_to_seed_sql.py -s ./data/stardict.db -o D:/kaoyan.sql

    # 也支持 stardict.csv
    python scripts/ecdict_to_seed_sql.py -s ./data/stardict.csv

    # 导入 MySQL (PowerShell 不支持 < 重定向，用下面任一方式)
    #   Get-Content seed_kaoyan_english2.sql -Raw | mysql -uroot -p<db>
    #   cmd /c "mysql -uroot -p<db> < seed_kaoyan_english2.sql"

====================================================================
 生成规则（与 import_ecdict.py 完全一致）
====================================================================
筛选: tag 含 'ky' (考研大纲词)
分组（按 collins 词频，3 个 Unit）:
    - 考研·高频核心   collins >= 4            （全部 🔥 high_freq）
    - 考研·常用       collins in (2, 3)       （oxford=1 的额外 🔥）
    - 考研·基础       collins <= 1 或缺失      （oxford=1 的额外 🔥）
标签: 全部 📚 exam_focus；高频词额外 🔥 high_freq
幂等: SQL 开头 DELETE FROM unit WHERE title LIKE '考研·%'（word/word_tags 级联删除）
序号: unit.sequence 接在 MAX(sequence) 之后，避免与现有 unit 冲突

本脚本不连数据库、不依赖 app/SQLAlchemy —— 只读 ECDICT 文件、写 SQL 文本，
便于把生成的 .sql 提交进 git 反复使用。需要直接写库时改用 import_ecdict.py。
"""
import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台中文输出
except (AttributeError, ValueError):
    pass


# (Unit 标题, collins 分组谓词) —— 与 import_ecdict.py 的 UNIT_DEFS 保持一致
UNIT_DEFS = [
    ("考研·高频核心", lambda c: c is not None and c >= 4),
    ("考研·常用",     lambda c: c is not None and 2 <= c <= 3),
    ("考研·基础",     lambda c: c is None or c <= 1),
]
KY_UNIT_PREFIX = "考研·"
CHINESE_MAX_LEN = 500      # Word.chinese 字段长度上限
HIGHFREQ_IN_CHUNK = 500    # english IN (...) 每块最大词数，避免单条 SQL 过长


def _parse_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _normalize(row):
    return {
        "word": (row.get("word") or "").strip(),
        "translation": (row.get("translation") or "").strip(),
        "collins": _parse_int(row.get("collins")),
        "oxford": _parse_int(row.get("oxford")),
    }


def load_ky_words(source):
    """读取 ECDICT 文件，返回考研词列表（已 _normalize，已过滤空 word）。"""
    ext = os.path.splitext(source)[1].lower()
    rows = []
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
                "word": r["word"], "translation": r["translation"],
                "collins": r["collins"], "oxford": r["oxford"], "tag": r["tag"],
            }))
        conn.close()
    else:
        raise ValueError(f"不支持的文件格式: {ext}（请提供 .csv 或 .db）")
    return [r for r in rows if r["word"]]


def assign_unit(collins):
    for title, pred in UNIT_DEFS:
        if pred(collins):
            return title
    return UNIT_DEFS[-1][0]  # 兜底进基础组


def is_high_freq(row):
    return (row["collins"] is not None and row["collins"] >= 4) or row["oxford"] == 1


def sql_escape(s):
    """转义 MySQL 字符串字面量。先反斜杠、再单引号，最后真换行转字面 \\n。"""
    return (s.replace("\\", "\\\\")
             .replace("'", "''")
             .replace("\n", "\\n")
             .replace("\r", "\\r"))


def sql_str(s):
    return "'" + sql_escape(s) + "'"


def build_sql(rows):
    """根据考研词列表生成完整 SQL 文本。"""
    groups = {t: [] for t, _ in UNIT_DEFS}
    for r in rows:
        groups[assign_unit(r["collins"])].append(r)

    total = len(rows)
    total_hf = sum(1 for r in rows if is_high_freq(r))

    L = []
    A = L.append
    A("-- ============================================================")
    A("-- 考研英语(二)大纲词种子  (自动生成，请勿手改；重跑覆盖)")
    A(f"-- 来源: ECDICT (tag=ky), 共 {total} 词, 高频标签 {total_hf} 个")
    A("-- 分组: 高频核心 / 常用 / 基础  (按 collins 词频)")
    A("-- 标签: 全部 📚 exam_focus; 高频词额外 🔥 high_freq")
    A("-- 适配表: unit / word / word_tags (外键均 ON DELETE CASCADE)")
    A("-- 字符集: utf8mb4")
    A("-- 幂等: 开头按 title LIKE '考研·%' 删除旧 unit; word/word_tags 级联删除, 可安全重跑")
    A("-- 序号: unit.sequence 接在 MAX(sequence) 之后, 不与现有 unit 冲突")
    A("-- ============================================================")
    A("")
    A("SET NAMES utf8mb4;")
    A("START TRANSACTION;")
    A("")
    A(f"DELETE FROM unit WHERE title LIKE '{KY_UNIT_PREFIX}%';")
    A("")
    A("-- 接在现有最大 sequence 之后，避免唯一约束冲突")
    A("SET @base := (SELECT COALESCE(MAX(sequence), 0) FROM unit);")
    A("")

    for idx, (title, _) in enumerate(UNIT_DEFS):
        items = groups[title]
        A(f"-- ---------- {title} ({len(items)} 词) ----------")
        A("INSERT INTO unit (title, sequence, created_at, updated_at)")
        A(f"  VALUES ({sql_str(title)}, @base + {idx + 1}, NOW(), NOW());")
        A("SET @u := LAST_INSERT_ID();")
        A("")

        if not items:
            A("-- (本组无词)")
            A("")
            continue

        # 批量插入 word（紧凑多行 VALUES，风格同 seed_18_units.sql）
        A("INSERT INTO word (unit_id, english, chinese, seq, type, created_at, updated_at) VALUES")
        word_lines = []
        for i, r in enumerate(items, 1):
            cn = r["translation"][:CHINESE_MAX_LEN] or r["word"]
            word_lines.append(
                f"  (@u, {sql_str(r['word'])}, {sql_str(cn)}, {i}, 'word', NOW(), NOW())"
            )
        A(",\n".join(word_lines) + ";")
        A("")

        # 全部打 exam_focus（按 unit_id 全量关联，无需逐条取 word.id）
        A("-- 📚 全部打 exam_focus")
        A("INSERT INTO word_tags (word_id, tag)")
        A("  SELECT id, 'exam_focus' FROM word WHERE unit_id = @u;")

        # 高频词打 high_freq
        hf_words = [r["word"] for r in items if is_high_freq(r)]
        if idx == 0:
            # 高频核心组：collins>=4，全部高频
            A("-- 🔥 高频核心组全部 high_freq")
            A("INSERT INTO word_tags (word_id, tag)")
            A("  SELECT id, 'high_freq' FROM word WHERE unit_id = @u;")
        elif hf_words:
            # 常用/基础组：仅 oxford=1 的高频词，按 english IN (...) 关联，分块
            n_chunks = (len(hf_words) + HIGHFREQ_IN_CHUNK - 1) // HIGHFREQ_IN_CHUNK
            A(f"-- 🔥 高频词 (oxford=1) 共 {len(hf_words)} 个" +
              (f"，分 {n_chunks} 块" if n_chunks > 1 else ""))
            for j in range(0, len(hf_words), HIGHFREQ_IN_CHUNK):
                chunk = hf_words[j:j + HIGHFREQ_IN_CHUNK]
                in_list = ", ".join(sql_str(w) for w in chunk)
                A("INSERT INTO word_tags (word_id, tag)")
                A(f"  SELECT id, 'high_freq' FROM word WHERE unit_id = @u AND english IN ({in_list});")
        A("")

    A("COMMIT;")
    A("")
    A("-- ---- 校验 ----")
    A("-- SELECT u.title, COUNT(w.id) AS words,")
    A("--        SUM(CASE WHEN t.tag='high_freq' THEN 1 ELSE 0 END) AS high_freq")
    A("-- FROM unit u")
    A("-- LEFT JOIN word w ON w.unit_id = u.id")
    A("-- LEFT JOIN word_tags t ON t.word_id = w.id AND t.tag='high_freq'")
    A("-- WHERE u.title LIKE '考研·%' GROUP BY u.title;")
    A("")
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(
        description="把 ECDICT 考研(英语二)词导出成幂等 SQL 种子文件"
    )
    parser.add_argument("--source", "-s", required=True,
                        help="ECDICT 文件路径 (.db/.sqlite/.sqlite3 或 .csv)")
    parser.add_argument("--output", "-o", default=None,
                        help="输出 SQL 路径，默认 backend/seed_kaoyan_english2.sql")
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"错误: 文件不存在 -> {args.source}")
        sys.exit(1)

    default_out = Path(__file__).resolve().parent.parent / "seed_kaoyan_english2.sql"
    out_path = Path(args.output) if args.output else default_out

    print(f"读取 ECDICT: {args.source}")
    rows = load_ky_words(args.source)
    print(f"筛选出考研词 (ky): {len(rows)} 个")
    for t, _ in UNIT_DEFS:
        n = sum(1 for r in rows if assign_unit(r["collins"]) == t)
        hf = sum(1 for r in rows if assign_unit(r["collins"]) == t and is_high_freq(r))
        print(f"  · {t}: {n} 个 (高频 {hf})")

    sql = build_sql(rows)
    out_path.write_text(sql, encoding="utf-8")
    line_count = sql.count("\n") + 1
    print(f"\n已生成 SQL: {out_path}  ({line_count} 行)")
    print("导入 MySQL:")
    print("  Get-Content seed_kaoyan_english2.sql -Raw | mysql -uroot -p<db>")
    print('  或:  cmd /c "mysql -uroot -p<db> < seed_kaoyan_english2.sql"')


if __name__ == "__main__":
    main()
