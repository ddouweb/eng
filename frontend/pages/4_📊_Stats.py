import streamlit as st
from api_client import client

st.header("📊 学习统计")

# ── 全局概览 ─────────────────────────────────────────
resp = client.list_units(page_size=100)
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有数据。")
    st.stop()

total_words = 0
level_counts = {"unlearned": 0, "learning": 0, "familiar": 0, "permanent": 0}

# ── 逐 Unit 统计 ─────────────────────────────────────
for unit in units:
    with st.container(border=True):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{unit['title']}**")

        w_resp = client.list_words(unit["id"], page_size=200)
        if w_resp["code"] != 200:
            continue

        words = w_resp["data"]["items"]
        total_words += len(words)

        unit_levels = {"unlearned": 0, "learning": 0, "familiar": 0, "permanent": 0}
        for w in words:
            mastery = w.get("mastery")
            level = mastery["level"] if mastery else "unlearned"
            unit_levels[level] += 1
            level_counts[level] += 1

        with col2:
            if len(words) > 0:
                learned = unit_levels["familiar"] + unit_levels["permanent"]
                pct = learned / len(words) * 100
                st.progress(pct / 100, text=f"掌握率 {pct:.0f}% ({learned}/{len(words)})")
            else:
                st.caption("暂无单词")

        level_colors = {"unlearned": "🔴", "learning": "🟠", "familiar": "🔵", "permanent": "🟢"}
        cols = st.columns(4)
        for i, (lv, cnt) in enumerate(unit_levels.items()):
            cols[i].metric(level_colors[lv] + " " + lv, cnt)

# ── 全局统计 ─────────────────────────────────────────
st.divider()
st.subheader("📈 全局概览")
col1, col2, col3, col4 = st.columns(4)
col1.metric("总单词数", total_words)
col2.metric("未学习", level_counts["unlearned"])
col3.metric("学习中", level_counts["learning"])
col4.metric("已掌握", level_counts["familiar"] + level_counts["permanent"])

if total_words > 0:
    mastered = level_counts["familiar"] + level_counts["permanent"]
    st.progress(mastered / total_words, text=f"总掌握率 {mastered / total_words * 100:.1f}%")
