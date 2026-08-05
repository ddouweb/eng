"""游戏化（坚持机制）的纯定义：徽章元数据 + XP 段位。

仅含常量与纯函数，无 DB 依赖。后端用于判定与下发；前端另存一份同名常量用于展示
（保持两端一致：增改徽章/段位时同步改 frontend 的 META）。
"""

# 徽章：key -> {name, icon, desc}。共 35 枚。判定逻辑见下方 *_THRESHOLDS 与各 service 钩子。
# 增改时务必同步 frontend-vue/src/constants/badges.ts（两端一致约定）。
BADGES = {
    # ── 连续学习 streak（阈值表 STREAK_BADGE_THRESHOLDS；签到/练习路径均可触发）──
    "streak_3":        {"name": "三日起步",   "icon": "🐣", "desc": "连续学习满 3 天"},
    "streak_7":        {"name": "一周坚持",   "icon": "🔥", "desc": "连续学习满 7 天"},
    "streak_10":       {"name": "十日养成",   "icon": "🌿", "desc": "连续学习满 10 天"},
    "streak_20":       {"name": "廿日成树",   "icon": "🌳", "desc": "连续学习满 20 天"},
    "streak_30":       {"name": "月度达人",   "icon": "🌙", "desc": "连续学习满 30 天"},
    "streak_40":       {"name": "四十不惑",   "icon": "🍀", "desc": "连续学习满 40 天"},
    "streak_50":       {"name": "半百达成",   "icon": "🎗️", "desc": "连续学习满 50 天"},
    "streak_60":       {"name": "花甲初度",   "icon": "🎴", "desc": "连续学习满 60 天"},
    "streak_70":       {"name": "古稀坚持",   "icon": "🎇", "desc": "连续学习满 70 天"},
    "streak_80":       {"name": "杖朝不辍",   "icon": "🎆", "desc": "连续学习满 80 天"},
    "streak_90":       {"name": "鲐背之年",   "icon": "🎰", "desc": "连续学习满 90 天"},
    "streak_100":      {"name": "百日不辍",   "icon": "💯", "desc": "连续学习满 100 天"},
    "streak_365":      {"name": "载入史册",   "icon": "🎉", "desc": "连续学习满 365 天"},
    # ── XP（阈值表 XP_BADGE_THRESHOLDS；答题加 XP 时触发）──
    "xp_100":          {"name": "初学乍练",   "icon": "🌱", "desc": "累计 100 XP"},
    "xp_1000":         {"name": "勤奋学子",   "icon": "⭐", "desc": "累计 1000 XP"},
    "xp_5000":         {"name": "词汇大师",   "icon": "🏆", "desc": "累计 5000 XP"},
    "xp_10000":        {"name": "万众瞩目",   "icon": "🎖️", "desc": "累计 10000 XP"},
    # ── 掌握度（答题后按永久掌握词数判定）──
    "first_permanent": {"name": "牢记在心",   "icon": "🧠", "desc": "首个单词达到永久掌握"},
    "permanent_50":    {"name": "初窥门径",   "icon": "🧩", "desc": "永久掌握 50 个单词"},
    "permanent_200":   {"name": "熟能生巧",   "icon": "🏅", "desc": "永久掌握 200 个单词"},
    "permanent_500":   {"name": "融会贯通",   "icon": "🎓", "desc": "永久掌握 500 个单词"},
    # ── 练习量 / 质量（答题后按累计题数 / 正确率判定）──
    "practice_500":    {"name": "勤学不倦",   "icon": "📝", "desc": "累计答题 500 次"},
    "practice_2000":   {"name": "笔耕不辍",   "icon": "✍️", "desc": "累计答题 2000 次"},
    "practice_5000":   {"name": "题海达人",   "icon": "🚀", "desc": "累计答题 5000 次"},
    "accuracy_90":     {"name": "精准射手",   "icon": "🎯", "desc": "累计正确率 ≥90%（且 ≥200 题）"},
    # ── 模式探索（完成练习时按用过的模式数判定）──
    "modes_explorer":  {"name": "十项全能",   "icon": "🎲", "desc": "使用过 10 种练习模式"},
    # ── 错题本（清零时判定）──
    "wrongbook_clear": {"name": "扫清障碍",   "icon": "🧹", "desc": "错题本清零（无未掌握错题）"},
    # ── 周结算（settle 时判定）──
    "week_full_score": {"name": "满分周",     "icon": "🌟", "desc": "单周结算满分 100"},
    "week_login_7":    {"name": "全勤周",     "icon": "📅", "desc": "单周 7 天全部学习"},
    "stars_total_30":  {"name": "星光璀璨",   "icon": "✨", "desc": "累计获得 30 颗星"},
    "perfect_weeks_4": {"name": "稳如磐石",   "icon": "📊", "desc": "累计 4 个满分周"},
    "unit_master_1":   {"name": "攻克一册",   "icon": "📖", "desc": "背完 1 个 Unit（全部掌握）"},
    "unit_master_5":   {"name": "攻克五册",   "icon": "📚", "desc": "背完 5 个 Unit"},
    "plan_complete_1": {"name": "圆满开局",   "icon": "📋", "desc": "完成 1 个学习计划"},
    "plan_complete_5": {"name": "计划通",     "icon": "🗓️", "desc": "完成 5 个学习计划"},
}

# (阈值, badge_key) —— 达到阈值即发放（幂等）。streak 走签到/练习两条路径。
STREAK_BADGE_THRESHOLDS = [
    (3, "streak_3"), (7, "streak_7"), (10, "streak_10"), (20, "streak_20"),
    (30, "streak_30"), (40, "streak_40"), (50, "streak_50"), (60, "streak_60"),
    (70, "streak_70"), (80, "streak_80"), (90, "streak_90"), (100, "streak_100"),
    (365, "streak_365"),
]
XP_BADGE_THRESHOLDS = [(100, "xp_100"), (1000, "xp_1000"), (5000, "xp_5000"), (10000, "xp_10000")]
# 永久掌握词数 / 累计答题数（答题后判定，与 streak/xp 同在 _check_and_award_badges 循环）
PERMANENT_BADGE_THRESHOLDS = [(50, "permanent_50"), (200, "permanent_200"), (500, "permanent_500")]
PRACTICE_BADGE_THRESHOLDS = [(500, "practice_500"), (2000, "practice_2000"), (5000, "practice_5000")]

# 段位：(累计 XP 下限, 段位名, 图标)
LEVELS = [
    (0, "青铜", "🥉"),
    (100, "白银", "🥈"),
    (300, "黄金", "🥇"),
    (600, "铂金", "💠"),
    (1000, "钻石", "💎"),
    (2000, "大师", "👑"),
]

MAX_FREEZE_BALANCE = 5


def xp_to_level(total_xp: int) -> dict:
    """根据累计 XP 返回当前段位与到下一段位的进度（0~1）。

    大师（最高段位）封顶后不再升段，而是每 1000 XP 折一颗 ★，星数无上限、
    永不满级：stars = floor((xp - 大师线) / 1000)，即 2000→0、3000→1、4525→2。
    星直接拼进 level_name / next_level_name，且 next_level_min_xp 永远指向
    下一颗星，因此前端「满级」分支不再触发、进度条继续走，无需前端改动。
    """
    xp = max(0, int(total_xp or 0))
    cur_idx = 0
    for i, (lo, _name, _icon) in enumerate(LEVELS):
        if xp >= lo:
            cur_idx = i
    lo, name, icon = LEVELS[cur_idx]
    if cur_idx + 1 < len(LEVELS):
        next_lo = LEVELS[cur_idx + 1][0]
        span = next_lo - lo
        progress = round((xp - lo) / span, 3) if span > 0 else 1.0
        next_name = LEVELS[cur_idx + 1][1]
        stars = 0
    else:
        # 大师封顶后：每 1000 XP 一颗 ★，星数无上限、永不满级。
        stars = (xp - lo) // 1000
        cur_lo = lo + stars * 1000       # 当前星段下限
        next_lo = cur_lo + 1000          # 下一颗星阈值（永远存在 → 不满级）
        progress = round((xp - cur_lo) / 1000, 3)
        name = f"{name}{'★' * stars}"
        next_name = f"{LEVELS[cur_idx][1]}{'★' * (stars + 1)}"
    return {
        "level_index": cur_idx,
        "level_name": name,
        "level_icon": icon,
        "level_min_xp": lo,
        "next_level_min_xp": next_lo,
        "next_level_name": next_name,
        "progress": progress,
        "stars": stars,
    }


def difficulty_mult(mastery) -> float:
    """根据掌握度算逐题 XP 难度乘数 ∈ [0.5, 2.0]。

    纯函数，仅读 mastery 现有字段（零额外查询）。难度信号均为答题后状态
    （PracticeService 在调用前已完成 _update_mastery / update_srs）：
    - wrong_count：反复遗忘→难（0.4 × min(wrong/3, 1)，3 次封顶）；
    - level∈{unlearned,learning}：尚未驯服→难（+0.3）；
    - ease_factor<2.5：SM-2 已下调难度→难（+0.3 × max(0, 2.5-ease)，基准 2.5）。
    下界实际 1.0（已 familiar/permanent 且无错的词），clamp[0.5,2.0] 仅作兜底。
    mastery 为 None（无记录）→ 1.0。
    """
    if mastery is None:
        return 1.0
    wrong = int(getattr(mastery, "wrong_count", 0) or 0)
    level = getattr(mastery, "level", None)
    ease = float(getattr(mastery, "ease_factor", 2.5) or 2.5)
    m = 1.0
    m += 0.4 * min(wrong / 3.0, 1.0)
    if level in ("unlearned", "learning"):
        m += 0.3
    m += 0.3 * max(0.0, 2.5 - ease)
    return max(0.5, min(2.0, m))
