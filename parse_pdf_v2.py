"""
parse_pdf_v2.py — Coordinate-based PDF parser for 18章答案.pdf

Strategy:
1. CJK span x-clustering → 3 CN anchor positions per page
2. Per column, find NO anchor from digit spans left of CN
3. Assign spans to columns by proximity to CN/NO anchors
4. Process each column: find NO+EN pairs, midpoint zones, collect CJK meanings
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz

PDF_PATH = Path(__file__).parent / "18章答案.pdf"
SQL_PATH = Path(__file__).parent / "backend" / "init_data.sql"

PAGE_HEIGHT = 842
PAGE_WIDTH = 596

EXPECTED = {
    1: 80, 2: 85, 3: 84, 4: 97, 5: 94, 6: 94,
    7: 102, 8: 86, 9: 103, 10: 96, 11: 107, 12: 99,
    13: 108, 14: 85, 15: 102, 16: 92, 17: 98, 18: 86,
}


@dataclass
class RawSpan:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    font: str
    size: float


@dataclass
class ColAnchors:
    no_x: float      # median x0 of NO numbers
    cn_x: float      # median x0 of CJK meanings
    cn_x_right: float  # max x1 of CJK meanings


@dataclass
class Entry:
    unit_id: int
    no: int
    english: str
    chinese: str


def has_cjk(text: str) -> bool:
    return any(0x4E00 <= ord(c) <= 0x9FFF or 0x3400 <= ord(c) <= 0x4DBF
               or 0x3000 <= ord(c) <= 0x303F or 0xFF00 <= ord(c) <= 0xFFEF
               for c in text)


def is_latin_word(text: str) -> bool:
    t = text.strip()
    return bool(t) and not t.isdigit() and not has_cjk(t)


def extract_spans(page) -> list[RawSpan]:
    result = []
    data = page.get_text("dict")
    for block in data["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"]
                x0, y0, x1, y1 = span["bbox"]
                # Split CJK text with trailing digits into two spans
                # e.g. "坚强的/坚强地68" → "坚强的/坚强地" + "68"
                m = re.match(r'^(.*[一-鿿　-〿＀-￯])(\d+)$', text)
                if m:
                    cjk_part, digit_part = m.group(1), m.group(2)
                    # Estimate x position of digit part
                    ratio = len(digit_part) / len(text) if text else 0
                    digit_x0 = x1 - (x1 - x0) * ratio
                    result.append(RawSpan(
                        x0=x0, y0=y0, x1=digit_x0, y1=y1,
                        text=cjk_part, font=span["font"], size=span["size"],
                    ))
                    result.append(RawSpan(
                        x0=digit_x0, y0=y0, x1=x1, y1=y1,
                        text=digit_part, font=span["font"], size=span["size"],
                    ))
                else:
                    result.append(RawSpan(
                        x0=x0, y0=y0, x1=x1, y1=y1,
                        text=text, font=span["font"], size=span["size"],
                    ))
    return result


def page_to_unit(page_idx: int) -> int:
    return 17 if page_idx == 16 else page_idx + 1


def detect_header_y(spans: list[RawSpan]) -> float:
    max_y = 0
    for s in spans:
        if s.y0 > 170:  # only check top of page
            continue
        t = s.text.strip()
        if not t:
            continue
        if any(kw in t for kw in ['NO', '单词', '释义', '学生姓名', '日期',
                                    '总词数', '错误数', '成都新东方', '高频词汇']):
            if s.y1 > max_y:
                max_y = s.y1
    return max_y if max_y > 0 else 120


def cluster_into_3(values: list[float]) -> list[list[float]]:
    if len(values) < 3:
        return [values]
    sv = sorted(values)
    gaps = [(sv[i] - sv[i-1], i) for i in range(1, len(sv))]
    gaps.sort(reverse=True)
    if len(gaps) < 2:
        return [sv]
    s1 = min(gaps[0][1], gaps[1][1])
    s2 = max(gaps[0][1], gaps[1][1])
    return [sv[:s1], sv[s1:s2], sv[s2:]]


def detect_columns(spans: list[RawSpan], header_y: float) -> list[ColAnchors]:
    """Detect 3 columns by CJK x-clustering for CN, then assign digits to columns."""
    content = [s for s in spans if s.y0 >= header_y]

    # Step 1: CJK span x0 clustering → 3 CN positions
    cjk_x = sorted({s.x0 for s in content if has_cjk(s.text.strip())})
    if len(cjk_x) < 3:
        return []

    cjk_groups = cluster_into_3(cjk_x)
    if len(cjk_groups) != 3 or any(len(g) == 0 for g in cjk_groups):
        return []

    cn_positions = [g[len(g)//2] for g in cjk_groups]

    # CN right edges
    cn_right_edges = []
    for grp in cjk_groups:
        cn_min, cn_max = min(grp) - 5, max(grp) + 5
        x1s = [s.x1 for s in content if has_cjk(s.text.strip()) and cn_min <= s.x0 <= cn_max]
        cn_right_edges.append(max(x1s) if x1s else grp[-1] + 40)

    # Step 2: Assign digit spans to columns
    # A digit span belongs to the column whose CN is the next one to the RIGHT
    all_digit_x = sorted({s.x0 for s in content if s.text.strip().isdigit()})
    col_digits: list[list[float]] = [[] for _ in range(3)]

    for dx in all_digit_x:
        # Find which column this digit belongs to
        # Column boundary: midpoint between adjacent CN positions
        # But we use "next CN to the right" for assignment
        assigned = False
        for ci in range(3):
            cn_left = cn_positions[ci - 1] if ci > 0 else 0
            cn_right = cn_positions[ci]
            # Digit is between previous CN and this CN → belongs to this column
            if cn_left < dx < cn_right:
                col_digits[ci].append(dx)
                assigned = True
                break
        if not assigned:
            # Digit is to the right of the last CN → belongs to last column
            if dx > cn_positions[2]:
                col_digits[2].append(dx)
            # Digit is to the left of the first CN → belongs to first column
            elif dx < cn_positions[0]:
                col_digits[0].append(dx)

    # Step 3: For each column, split digits into NO (left) and meaning (right)
    no_positions = []
    for ci in range(3):
        digits = sorted(col_digits[ci])
        if len(digits) == 0:
            no_positions.append(cn_positions[ci] - 80)
            continue
        if len(digits) == 1:
            no_positions.append(digits[0])
            continue
        # Find largest gap → splits NO (left group) from meaning (right group)
        best_gap, best_split = 0, len(digits) // 2
        for j in range(1, len(digits)):
            g = digits[j] - digits[j-1]
            if g > best_gap:
                best_gap = g
                best_split = j
        no_group = digits[:best_split] if best_split > 0 else digits
        no_positions.append(no_group[len(no_group)//2])

    columns = []
    for i in range(3):
        columns.append(ColAnchors(
            no_x=no_positions[i],
            cn_x=cn_positions[i],
            cn_x_right=cn_right_edges[i],
        ))
    return columns


def assign_span_to_column(span: RawSpan, columns: list[ColAnchors]) -> int:
    """Assign a span to the best-matching column."""
    t = span.text.strip()
    if not t:
        return -1

    # CJK text → closest CN anchor
    if has_cjk(t):
        dists = [abs(span.x0 - c.cn_x) for c in columns]
        return dists.index(min(dists))

    # Pure digits → closest NO anchor (within threshold) or CN anchor
    if t.isdigit():
        for i, c in enumerate(columns):
            if abs(span.x0 - c.no_x) < 25:
                return i
        # Not near any NO → meaning number, assign to closest CN
        dists = [abs(span.x0 - c.cn_x) for c in columns]
        return dists.index(min(dists))

    # Latin text → column whose [no_x, cn_x] range contains it
    for i, c in enumerate(columns):
        if c.no_x - 10 <= span.x0 <= c.cn_x + 10:
            return i
    # Fallback: closest column center
    centers = [(c.no_x + c.cn_x) / 2 for c in columns]
    dists = [abs(span.x0 - center) for center in centers]
    return dists.index(min(dists))


def parse_page(page, page_idx: int) -> list[Entry]:
    unit_id = page_to_unit(page_idx)
    spans = extract_spans(page)
    header_y = detect_header_y(spans)
    columns = detect_columns(spans, header_y)

    if not columns or len(columns) != 3:
        return []

    content = sorted([s for s in spans if s.y0 >= header_y and s.text.strip()],
                     key=lambda s: (s.y0, s.x0))

    # Assign each content span to a column
    col_spans: list[list[RawSpan]] = [[] for _ in range(3)]
    for s in content:
        ci = assign_span_to_column(s, columns)
        if ci >= 0:
            col_spans[ci].append(s)

    all_entries = []
    for ci, col in enumerate(columns):
        entries = process_column(col_spans[ci], col, unit_id)
        all_entries.extend(entries)

    return all_entries


def process_column(spans: list[RawSpan], col: ColAnchors, unit_id: int) -> list[Entry]:
    """Process spans in one column to extract entries."""
    spans = sorted(spans, key=lambda s: (s.y0, s.x0))

    # Find NO number anchors
    anchors = []
    for i, s in enumerate(spans):
        if not s.text.strip().isdigit():
            continue
        if abs(s.x0 - col.no_x) > 30:
            continue

        no_val = int(s.text.strip().lstrip('0'))
        no_y = s.y0

        # Collect English on same visual row (y within ±18 points, x between no and cn)
        english_parts = []
        for ns in spans:
            if ns is s:
                continue
            # Tighter y-window: EN must be closer to this NO than to adjacent anchors
            if abs(ns.y0 - no_y) > 18:
                continue
            # Skip if closer to a different NO number on same column
            other_no_closer = any(
                abs(ns.y0 - s2.y0) < abs(ns.y0 - no_y) and s2 is not s
                for s2 in spans
                if s2.text.strip().isdigit() and abs(s2.x0 - col.no_x) < 30
                and s2 is not s
            )
            if other_no_closer:
                continue
            nt = ns.text.strip()
            if nt and is_latin_word(nt) and s.x0 < ns.x0 < col.cn_x - 5:
                english_parts.append(nt)

        anchors.append({
            'no': no_val,
            'english': ' '.join(english_parts),
            'no_y': no_y,
        })

    if not anchors:
        return []

    # Fix duplicate NOs caused by PDF printing errors
    # E.g. [35, 35, 37] → [35, 36, 37] or [79, 81, 81, 82] → [79, 80, 81, 82]
    all_nos = [a['no'] for a in anchors]
    unique_nos = set(all_nos)
    for n in list(unique_nos):
        if all_nos.count(n) < 2:
            continue
        # Find which adjacent number is missing
        n_minus_1_missing = n - 1 not in unique_nos
        n_plus_1_missing = n + 1 not in unique_nos
        if not n_minus_1_missing and not n_plus_1_missing:
            continue
        # Get indices of duplicates
        dup_indices = [i for i, a in enumerate(anchors) if a['no'] == n]
        if n_minus_1_missing:
            # Renumber the FIRST duplicate to n-1
            anchors[dup_indices[0]]['no'] = n - 1
        elif n_plus_1_missing:
            # Renumber the LAST duplicate to n+1
            anchors[dup_indices[-1]]['no'] = n + 1

    # Handle multi-line English
    for ai, anchor in enumerate(anchors):
        next_y = anchors[ai + 1]['no_y'] if ai + 1 < len(anchors) else PAGE_HEIGHT
        for s in spans:
            if s.y0 <= anchor['no_y'] + 18:
                continue
            if s.y0 >= next_y:
                break
            t = s.text.strip()
            if t and is_latin_word(t) and col.no_x - 10 <= s.x0 <= col.cn_x:
                has_no = any(abs(s2.y0 - s.y0) < 12 and s2.text.strip().isdigit()
                             and abs(s2.x0 - col.no_x) < 25 for s2 in spans)
                if not has_no:
                    anchor['english'] += t

    # Collect meanings using midpoint zones with dedup
    used_cn_spans = set()
    entries = []
    for ai, anchor in enumerate(anchors):
        y_top = (anchors[ai - 1]['no_y'] + anchor['no_y']) / 2 if ai > 0 else 0
        y_bottom = (anchor['no_y'] + anchors[ai + 1]['no_y']) / 2 if ai + 1 < len(anchors) else PAGE_HEIGHT

        cn_parts = []
        for s in spans:
            if id(s) in used_cn_spans:
                continue
            if s.y0 < y_top or s.y0 > y_bottom:
                continue
            t = s.text.strip()
            if not t:
                continue

            # CJK text
            if has_cjk(t):
                m = re.match(r'^(\d)([^\d].*)$', t)
                if m and has_cjk(m.group(2)):
                    cn_parts.append(f"{m.group(1)} {m.group(2)}")
                else:
                    cn_parts.append(t)
                used_cn_spans.add(id(s))
            # Meaning number (digit span near CN, not near NO)
            elif t.isdigit() and abs(s.x0 - col.cn_x) < 30 and abs(s.x0 - col.no_x) > 50:
                cn_parts.append(t)
                used_cn_spans.add(id(s))

        chinese = re.sub(r'\s+', ' ', ' '.join(cn_parts)).strip()
        entries.append(Entry(
            unit_id=unit_id, no=anchor['no'],
            english=anchor['english'].strip(), chinese=chinese,
        ))

    return entries


def parse_pdf(pdf_path: Path) -> list[Entry]:
    doc = fitz.open(str(pdf_path))
    all_entries = []
    for page_idx in range(len(doc)):
        all_entries.extend(parse_page(doc[page_idx], page_idx))

    # Deduplicate: merge entries with same (unit_id, no)
    merged = {}
    for e in all_entries:
        key = (e.unit_id, e.no)
        if key in merged:
            existing = merged[key]
            # Merge: prefer non-empty english, combine chinese
            if not existing.english and e.english:
                existing.english = e.english
            elif existing.english and e.english and e.english not in existing.english:
                existing.english = existing.english + ' ' + e.english
            if e.chinese and e.chinese not in existing.chinese:
                existing.chinese = existing.chinese + ' ' + e.chinese
        else:
            merged[key] = Entry(unit_id=e.unit_id, no=e.no,
                                english=e.english, chinese=e.chinese)

    # Manual fixes for entries completely invisible to pymupdf
    MANUAL_FIXES = {
        (18, 41): Entry(unit_id=18, no=41, english='dead', chinese='死亡的'),
    }
    # Fix entries with wrong CN due to midpoint boundary issues
    MANUAL_CN_FIXES = {
        (7, 68): '1 移动 2 运动',
        (7, 69): '核能的',
        (18, 40): '损害',
    }
    # Also clean up adjacent entries contaminated by missing anchors
    MANUAL_ADJACENT_CLEANUP = {
        (18, 40): ('damage', None),  # contaminated with 'dead c'
        (18, 42): ('delay', None),
    }
    for key, entry in MANUAL_FIXES.items():
        if key not in merged:
            merged[key] = entry
            print(f"  MANUAL FIX: U{entry.unit_id} NO{entry.no}: en='{entry.english}' cn='{entry.chinese}'")
    for key, cn_fix in MANUAL_CN_FIXES.items():
        if key in merged:
            merged[key].chinese = cn_fix
    for key, (en_fix, cn_fix) in MANUAL_ADJACENT_CLEANUP.items():
        if key in merged:
            e = merged[key]
            if en_fix is not None:
                e.english = en_fix
            if cn_fix is not None:
                e.chinese = cn_fix

    return sorted(merged.values(), key=lambda e: (e.unit_id, e.no))


def generate_sql(entries: list[Entry], output_path: Path):
    lines = [
        "-- ============================================",
        "-- Family English Coach - 初始化脚本",
        "-- 从 18章答案.pdf 提取, 18单元 (coordinate-based parser v2)",
        "-- ============================================",
        "", "SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS = 0;", "",
        "TRUNCATE TABLE word_tags;", "TRUNCATE TABLE mastery_record;",
        "TRUNCATE TABLE practice_record;", "TRUNCATE TABLE practice_session;",
        "TRUNCATE TABLE daily_task;", "TRUNCATE TABLE plan_units;",
        "TRUNCATE TABLE learning_plan;", "TRUNCATE TABLE word;",
        "TRUNCATE TABLE unit;", "TRUNCATE TABLE member;", "",
        "INSERT INTO member (id, name, avatar, created_at, updated_at) VALUES",
        "  (1, '默认用户', NULL, NOW(), NOW());", "",
        "INSERT INTO unit (id, title, sequence, image_url, created_at, updated_at) VALUES",
    ]
    for i in range(1, 19):
        comma = "," if i < 18 else ";"
        lines.append(f"  ({i}, 'Unit {i}', {i}, NULL, NOW(), NOW()){comma}")
    lines.append("")
    lines.append("INSERT INTO word (id, unit_id, english, chinese, type, created_at, updated_at) VALUES")
    for i, e in enumerate(entries):
        en = e.english.replace("'", "''").strip()
        cn = e.chinese.replace("'", "''").strip()
        comma = "," if i < len(entries) - 1 else ";"
        lines.append(f"  ({i + 1}, {e.unit_id}, '{en}', '{cn}', 'word', NOW(), NOW()){comma}")
    lines.append("")
    lines.append(f"-- 单元: 18 | 单词: {len(entries)}")
    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def validate(entries: list[Entry]) -> bool:
    ok = True
    unit_counts = {}
    for e in entries:
        unit_counts[e.unit_id] = unit_counts.get(e.unit_id, 0) + 1
    total = 0
    for uid in range(1, 19):
        count = unit_counts.get(uid, 0)
        exp = EXPECTED[uid]
        total += count
        st = "OK" if count == exp else "MISMATCH"
        if count != exp: ok = False
        print(f"  Unit {uid:2d}: {count:3d} / {exp:3d}  {st}")
    print(f"\n  Total: {total} / 1698")
    if total != 1698: ok = False

    empty_en = [e for e in entries if not e.english.strip()]
    empty_cn = [e for e in entries if not e.chinese.strip()]
    if empty_en:
        print(f"\n  WARNING: {len(empty_en)} empty english")
        for e in empty_en[:5]:
            print(f"    Unit {e.unit_id} NO {e.no}")
    if empty_cn:
        print(f"\n  WARNING: {len(empty_cn)} empty chinese")
        for e in empty_cn[:5]:
            print(f"    Unit {e.unit_id} NO {e.no}: {e.english}")
    return ok


def spot_check(entries: list[Entry]):
    print("\n=== Spot Checks ===")
    checks = [
        (1, 9, "state", ["国家", "州", "状态", "说"]),
        (1, 8, "social", ["社会的", "社交的"]),
        (18, 86, "found", ["建立", "找到", "发现"]),
    ]
    entry_map = {(e.unit_id, e.no): e for e in entries}
    with open("spot_check_result.txt", "w", encoding="utf-8") as f:
        for uid, no, en, parts in checks:
            e = entry_map.get((uid, no))
            if not e:
                print(f"  MISSING: U{uid} NO{no} ({en})")
                f.write(f"MISSING: U{uid} NO{no} ({en})\n")
                continue
            ok = all(p in e.chinese for p in parts)
            st = "OK" if ok else "MISMATCH"
            print(f"  {st}: U{uid} NO{no} '{e.english}'")
            f.write(f"{st}: U{uid} NO{no} '{e.english}' = '{e.chinese}'\n")
            if not ok:
                f.write(f"  Missing: {[p for p in parts if p not in e.chinese]}\n")


if __name__ == "__main__":
    print("Parsing PDF (v2 proximity-based)...")
    entries = parse_pdf(PDF_PATH)
    print(f"\nExtracted {len(entries)} entries\n")
    validate(entries)
    spot_check(entries)
    print(f"\nGenerating SQL...")
    generate_sql(entries, SQL_PATH)
    print("Done.")
