import pandas as pd
import streamlit as st
from api_client import client

st.header("🏆 家庭排行榜")

resp = client.get_leaderboard()
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

members = resp["data"]["members"]
if not members:
    st.info("暂无成员数据。")
    st.stop()

# ── 排行表格 ────────────────────────────────────────────
st.subheader("学习排行")
table_data = []
for i, m in enumerate(members):
    table_data.append({
        "排名": i + 1,
        "成员": m["name"],
        "已掌握": m["mastered_count"],
        "掌握率": f"{m['mastery_rate']}%",
        "正确率": f"{m['accuracy']}%",
        "连续学习": f"{m['streak_days']} 天",
        "练习次数": m["session_count"],
    })
st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

# ── 掌握进度对比 ─────────────────────────────────────────
st.subheader("掌握进度对比")
total_words = members[0]["total_words"] or 1
progress_data = []
for m in members:
    progress_data.append({
        "成员": m["name"],
        "已掌握": m["mastered_count"],
        "未掌握": max(m["total_words"] - m["mastered_count"], 0),
    })
progress_df = pd.DataFrame(progress_data)
st.bar_chart(progress_df.set_index("成员"), use_container_width=True)

# ── 正确率对比 ───────────────────────────────────────────
st.subheader("正确率对比 (%)")
acc_data = [{"成员": m["name"], "正确率": m["accuracy"]} for m in members if m["total_questions"] > 0]
if acc_data:
    st.bar_chart(pd.DataFrame(acc_data).set_index("成员"), use_container_width=True)
else:
    st.info("暂无练习记录。")

# ── 连续学习天数对比 ──────────────────────────────────────
st.subheader("连续学习天数")
streak_data = [{"成员": m["name"], "连续天数": m["streak_days"]} for m in members]
st.bar_chart(pd.DataFrame(streak_data).set_index("成员"), use_container_width=True)

# ── 掌握分布详情 ─────────────────────────────────────────
st.subheader("掌握分布详情")
level_labels = {"unlearned": "未学习", "learning": "学习中", "familiar": "熟悉", "permanent": "永久"}
for m in members:
    with st.container(border=True):
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**{m['name']}**")
        with col2:
            dist = m["mastery_distribution"]
            cols = st.columns(4)
            for i, (lv, label) in enumerate(level_labels.items()):
                cols[i].metric(label, dist.get(lv, 0))
