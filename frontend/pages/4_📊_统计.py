import pandas as pd
import streamlit as st
from api_client import client

st.header("📊 学习统计")

member_id = st.session_state.get("member_id", 1)

# ── 全局概览 ─────────────────────────────────────────
overview = client.get_stats_overview(member_id)
if overview["code"] != 200:
    st.error(overview["message"])
    st.stop()

data = overview["data"]
dist = data["mastery_distribution"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("总单词数", data["total_words"])
col2.metric("已掌握", data["mastered_count"])
col3.metric("练习次数", data["practice_session_count"])
col4.metric("连续学习", f"{data['streak_days']} 天")

col1, col2, col3 = st.columns(3)
col1.metric("掌握率", f"{data['mastery_rate']}%")
col2.metric("正确率", f"{data['accuracy']}%")
col3.metric("总答题数", data["total_questions"])

if data["total_words"] > 0:
    st.progress(
        data["mastered_count"] / data["total_words"],
        text=f"掌握率 {data['mastery_rate']}%",
    )

# ── 掌握分布 ─────────────────────────────────────────
st.subheader("掌握分布")
level_colors = {"unlearned": "🔴 未学习", "learning": "🟠 学习中", "familiar": "🔵 熟悉", "permanent": "🟢 永久"}
dist_df = pd.DataFrame([
    {"level": level_colors[k], "count": v}
    for k, v in dist.items()
])
st.bar_chart(dist_df, x="level", y="count", use_container_width=True)

# ── 按 Unit 统计 ─────────────────────────────────────
st.subheader("按 Unit 统计")
units_resp = client.list_all_units()
if units_resp["code"] == 200:
    for u in units_resp["data"]["items"]:
        stats = client.get_stats_unit(u["id"], member_id)
        if stats["code"] != 200:
            continue
        s = stats["data"]
        with st.container(border=True):
            col1, col2 = st.columns([3, 2])
            with col1:
                st.markdown(f"**{u['title']}**")
            with col2:
                st.progress(
                    s["mastered_count"] / s["total_words"] if s["total_words"] > 0 else 0,
                    text=f"掌握率 {s['mastery_rate']}%",
                )
            udist = s["mastery_distribution"]
            cols = st.columns(4)
            for i, (lv, label) in enumerate(level_colors.items()):
                cols[i].metric(label, udist[lv])

# ── 练习趋势 ─────────────────────────────────────────
st.subheader("练习趋势")
days_option = st.selectbox("时间范围", [7, 14, 30], format_func=lambda d: f"最近 {d} 天", key="trend_days")
trend = client.get_stats_trend(days=days_option, member_id=member_id)
if trend["code"] == 200 and trend["data"]["daily"]:
    trend_data = trend["data"]["daily"]
    trend_df = pd.DataFrame(trend_data)
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
