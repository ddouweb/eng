"""个人进步趋势页（原「家庭排行榜」，单人模式后改为自我纵向趋势）。

复用 stats 接口（profile / trend / overview）与统计页同款图表，零新后端。
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from api_client import client
from auth import require_auth

require_auth()
st.header("🏆 我的进步趋势")
st.caption("单人模式 · 追踪你自己的坚持与进步（连续打卡 · 练习趋势 · 掌握分布 · 个人最佳）。")

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

# ── 顶部：坚持指标（段位 / streak / XP / 徽章）──────────────
profile = client.get_stats_profile()
if profile["code"] != 200:
    st.error(profile["message"])
    st.stop()
p = profile["data"]
lv = p["level"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("🔥 连续学习", f"{p['current_streak']} 天")
c2.metric("🏆 最长记录", f"{p['longest_streak']} 天")
c3.metric("⭐ 累计 XP", p["total_xp"])
c4.metric(f"{lv['level_icon']} 段位", lv["level_name"])

if lv["next_level_min_xp"] is not None:
    st.progress(
        max(0.0, min(1.0, lv["progress"])),
        text=f"{lv['level_icon']} {lv['level_name']} → {lv['next_level_name']}",
    )
else:
    st.progress(1.0, text=f"{lv['level_icon']} {lv['level_name']}（满级）")

badges = p.get("badges") or []
if badges:
    chips = "  ".join(
        f"{BADGES_META.get(b, ('🏅', b))[0]} {BADGES_META.get(b, ('🏅', b))[1]}" for b in badges
    )
    st.markdown(f"**已获徽章：** {chips}")
else:
    st.caption("还没有徽章——连续学习 7 天、累计 100 XP 即可解锁第一个！")

st.divider()

# ── 12 周贡献热力图 ────────────────────────────────────
st.subheader("贡献热力图（最近 12 周）")
try:
    import altair as alt
    heat = client.get_stats_trend(days=84)
    if heat["code"] == 200 and heat["data"]["daily"]:
        cnt = {row["date"]: int(row["total"]) for row in heat["data"]["daily"]}
        today = date.today()
        rows = []
        for i in range(83, -1, -1):
            d = today - timedelta(days=i)
            ds = d.isoformat()
            rows.append({
                "date": ds, "count": cnt.get(ds, 0),
                "week": 11 - (i // 7),   # 左旧右新（0..11）
                "weekday": d.weekday(),  # 0=周一 .. 6=周日
            })
        hdf = pd.DataFrame(rows)
        chart = (
            alt.Chart(hdf)
            .mark_rect(stroke="white", strokeWidth=2)
            .encode(
                x=alt.X("week:O", title=None, axis=None),
                y=alt.Y("weekday:O", title=None, axis=None),
                color=alt.Color(
                    "count:Q",
                    scale=alt.Scale(domain=[0, max(10, int(hdf["count"].max()))],
                                    range=["#ebedf0", "#2da44e"]),
                    legend=None,
                ),
                tooltip=["date", "count"],
            )
            .properties(height=150)
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption("色块越绿＝当天练习量越大；空白＝当天未练习。")
    else:
        st.info("暂无练习记录，无法生成热力图。")
except ImportError:
    st.caption("（贡献热力图需 altair，当前环境未安装）")

# ── 练习趋势 ──────────────────────────────────────────
st.subheader("练习趋势")
days_option = st.selectbox(
    "时间范围", [7, 14, 30], format_func=lambda d: f"最近 {d} 天", key="trend_days_lb",
)
trend = client.get_stats_trend(days=days_option)
if trend["code"] == 200 and trend["data"]["daily"]:
    trend_df = pd.DataFrame(trend["data"]["daily"])
    trend_df["accuracy"] = (trend_df["correct"] / trend_df["total"].replace(0, 1) * 100).round(1)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.caption("每日练习量")
        st.bar_chart(trend_df, x="date", y="total", use_container_width=True)
    with col_chart2:
        st.caption("每日正确率 (%)")
        st.line_chart(trend_df, x="date", y="accuracy", use_container_width=True)
else:
    st.info("暂无练习记录。")

st.divider()

# ── 掌握分布 + 个人最佳 ────────────────────────────────
overview = client.get_stats_overview()
if overview["code"] == 200:
    data = overview["data"]
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("累计答题", data["total_questions"])
    col_b.metric("总正确率", f"{data['accuracy']}%")
    col_c.metric("已掌握", data["mastered_count"])

    st.subheader("掌握分布")
    level_colors = {"unlearned": "⚪ 未学习", "learning": "🟠 学习中", "familiar": "🔵 熟悉", "permanent": "🟢 永久"}
    dist_df = pd.DataFrame([
        {"level": level_colors[k], "count": v} for k, v in data["mastery_distribution"].items()
    ])
    st.bar_chart(dist_df, x="level", y="count", use_container_width=True)
else:
    st.caption(f"统计数据加载失败：{overview.get('message')}")
