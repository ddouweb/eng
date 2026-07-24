"""游戏化（坚持机制）的纯定义：徽章元数据 + XP 段位。

仅含常量与纯函数，无 DB 依赖。后端用于判定与下发；前端另存一份同名常量用于展示
（保持两端一致：增改徽章/段位时同步改 frontend 的 META）。
"""

# 徽章：key -> {name, icon, desc}。threshold 仅作文档，判定逻辑用下面的 *_THRESHOLDS。
BADGES = {
    "streak_7":       {"name": "一周坚持", "icon": "🔥", "desc": "连续学习满 7 天"},
    "streak_30":      {"name": "月度达人", "icon": "🌙", "desc": "连续学习满 30 天"},
    "streak_100":     {"name": "百日不辍", "icon": "💯", "desc": "连续学习满 100 天"},
    "xp_100":         {"name": "初学乍练", "icon": "🌱", "desc": "累计 100 XP"},
    "xp_1000":        {"name": "勤奋学子", "icon": "⭐", "desc": "累计 1000 XP"},
    "xp_5000":        {"name": "词汇大师", "icon": "🏆", "desc": "累计 5000 XP"},
    "first_permanent": {"name": "牢记在心", "icon": "🧠", "desc": "首个单词达到永久掌握"},
}

# (阈值, badge_key) —— 达到阈值即发放（幂等）
STREAK_BADGE_THRESHOLDS = [(7, "streak_7"), (30, "streak_30"), (100, "streak_100")]
XP_BADGE_THRESHOLDS = [(100, "xp_100"), (1000, "xp_1000"), (5000, "xp_5000")]

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
    """根据累计 XP 返回当前段位与到下一段位的进度（0~1）。"""
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
    else:
        next_lo = None
        progress = 1.0
        next_name = None
    return {
        "level_index": cur_idx,
        "level_name": name,
        "level_icon": icon,
        "level_min_xp": lo,
        "next_level_min_xp": next_lo,
        "next_level_name": next_name,
        "progress": progress,
    }
