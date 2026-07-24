import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from api_client import client
from auth import require_auth, clear_auth_cookie

st.set_page_config(page_title="家庭英语学习", page_icon="📚", layout="wide")

# 统一登录态校验：未登录或 token 失效时渲染登录表单并 stop()
require_auth()

# ── 已登录 ─────────────────────────────────────────────
st.title("📚 Family English Coach")
st.markdown("上传教材图片 → 自动生成单词库 → 练习 → 追踪掌握进度")

# 退出登录
st.sidebar.markdown("---")
if st.sidebar.button("🚪 退出登录"):
    client.set_token(None)
    st.session_state.token = None
    st.session_state.pop("_prac_units", None)
    clear_auth_cookie()
    st.rerun()

# ── 坚持机制卡片（streak / freeze / XP 段位 / 徽章 / 断签预警 / 回归引导）──
# 徽章元数据须与后端 app/gamification.py 的 BADGES 保持一致（增改时同步）
BADGES_META = {
    "streak_7":        ("🔥", "一周坚持"),
    "streak_30":       ("🌙", "月度达人"),
    "streak_100":      ("💯", "百日不辍"),
    "xp_100":          ("🌱", "初学乍练"),
    "xp_1000":         ("⭐", "勤奋学子"),
    "xp_5000":         ("🏆", "词汇大师"),
    "first_permanent": ("🧠", "牢记在心"),
}

profile = client.get_stats_profile()
if profile["code"] == 200:
    p = profile["data"]
    lv = p["level"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔥 连续学习", f"{p['current_streak']} 天")
    c2.metric("🛡️ 断签冻结", f"{p['freeze_balance']} 个")
    c3.metric("🏆 最长记录", f"{p['longest_streak']} 天")
    c4.metric(f"{lv['level_icon']} 段位", lv["level_name"])

    # XP 进度条（到下一段位）
    if lv["next_level_min_xp"] is not None:
        st.progress(
            max(0.0, min(1.0, lv["progress"])),
            text=f"{lv['level_icon']} {lv['level_name']} → {lv['next_level_name']}　·　累计 {p['total_xp']} XP",
        )
    else:
        st.progress(1.0, text=f"{lv['level_icon']} {lv['level_name']}（满级）　·　累计 {p['total_xp']} XP")

    # 断签预警 / 回归引导（基于持久化的 last_active_date）
    last = p.get("last_active_date")
    last_date = None
    if last:
        try:
            last_date = date.fromisoformat(last)
        except ValueError:
            last_date = None
    if last_date and last_date < date.today() and p["current_streak"] > 0:
        st.warning(
            f"⚠️ 你已连续 **{p['current_streak']}** 天，今天还没练习——"
            "别让记录断在今晚！(可用 🛡️ 冻结自动补一天)"
        )
    if last_date:
        gap = (date.today() - last_date).days
        if gap >= 3:
            st.info(f"👋 欢迎回来！上次练习在 {gap} 天前，从「🎯 练习」页的今日任务继续吧～")

    # 徽章
    badges = p.get("badges") or []
    if badges:
        chips = "  ".join(
            f"{BADGES_META.get(b, ('🏅', b))[0]} {BADGES_META.get(b, ('🏅', b))[1]}" for b in badges
        )
        st.markdown(f"**已获徽章：** {chips}")
    else:
        st.caption("还没有徽章——连续学习 7 天、累计 100 XP 即可解锁第一个！")
else:
    st.caption(f"坚持数据加载失败：{profile.get('message')}")

# ── 今日到期复习提示（SRS）──
_rd = client.get_review_due()
if _rd["code"] == 200:
    _d = _rd["data"]
    if _d["due_today"] > 0:
        _overdue_txt = f"（{_d['overdue']} 个已逾期）" if _d["overdue"] else ""
        st.warning(
            f"🔁 今天有 **{_d['due_today']}** 个单词到期复习{_overdue_txt}——"
            "去「🎯 练习」起一轮"
        )
        if st.button("🎯 去练习今日复习", type="primary"):
            st.switch_page("pages/3_🎯_练习.py")
    else:
        st.success("✅ 今天没有到期单词，可以学点新词或休息一下")
