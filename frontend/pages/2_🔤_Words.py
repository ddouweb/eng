import streamlit as st
from api_client import client

st.header("🔤 单词管理")

# ── 选择 Unit ────────────────────────────────────────
resp = client.list_units(page_size=100)
if resp["code"] != 200:
    st.error(f"加载失败: {resp['message']}")
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，请先到 Units 页面创建。")
    st.stop()

unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}
selected = st.selectbox("选择 Unit", list(unit_options.keys()))
unit_id = unit_options[selected]

# ── 手动添加单词 ─────────────────────────────────────
with st.expander("➕ 手动添加单词"):
    words_text = st.text_area("每行一个：英文,中文", placeholder="hello,你好\ngood morning,早上好")
    if st.button("批量添加"):
        lines = [l.strip() for l in words_text.strip().split("\n") if l.strip()]
        words = []
        for line in lines:
            parts = line.split(",", 1)
            if len(parts) == 2:
                words.append({"english": parts[0].strip(), "chinese": parts[1].strip(), "type": "word"})
        if words:
            resp = client.batch_create_words(unit_id, words)
            if resp["code"] == 200:
                st.success(f"添加 {resp['data']['created_count']} 个单词")
                st.rerun()
            else:
                st.error(resp["message"])

# ── 单词列表 ─────────────────────────────────────────
resp = client.list_words(unit_id, page_size=200)
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

words = resp["data"]["items"]
if not words:
    st.info("这个 Unit 还没有单词。")
    st.stop()

st.caption(f"共 {resp['data']['total']} 个单词")

TAG_OPTIONS = {
    "⭐ 收藏": "favorite",
    "🔥 高频": "high_freq",
    "📚 考试重点": "exam_focus",
    "❌ 不再练习": "excluded",
    "✅ 已记忆": "memorized",
}

for w in words:
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 3, 3, 1])
        with col1:
            st.markdown(f"**{w['english']}**")
        with col2:
            st.text(w["chinese"])
        with col3:
            mastery = w.get("mastery")
            if mastery:
                from components.mastery_badge import render as badge
                badge(mastery["level"], mastery.get("consecutive_correct", 0),
                      mastery.get("correct_count", 0), mastery.get("wrong_count", 0))
            else:
                st.caption("未学习")
        with col4:
            if st.button("🗑️", key=f"del_w_{w['id']}"):
                client.delete_word(w["id"])
                st.rerun()

        current_tags = w.get("tags", [])
        selected_labels = [k for k, v in TAG_OPTIONS.items() if v in current_tags]
        new_tags = st.multiselect("标签", list(TAG_OPTIONS.keys()), default=selected_labels,
                                  key=f"tags_{w['id']}")
        if set(new_tags) != set(selected_labels):
            tag_values = [TAG_OPTIONS[t] for t in new_tags]
            client.set_tags(w["id"], tag_values)
