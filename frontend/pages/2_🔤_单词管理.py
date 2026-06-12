import streamlit as st
from api_client import client
from components.ai_helpers import ai_kwargs, require_ai_key
from components.mastery_badge import MASTERY_COLORS

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

# ── AI 智能添加单词 ──────────────────────────────────
with st.expander("🤖 AI 智能添加单词"):
    st.caption("粘贴课文、单词列表或任意文本，AI 自动提取英语词条")
    nl_text = st.text_area(
        "输入文本",
        placeholder="例如：\n今天学习了 apple（苹果）、banana（香蕉）和 Good morning（早上好）",
        height=150,
        key="nl_input_text",
    )
    if st.button("AI 解析", disabled=not nl_text.strip()):
        if require_ai_key():
            with st.spinner("AI 正在解析文本..."):
                resp = client.parse_words(nl_text.strip(), **ai_kwargs())
            if resp["code"] == 200:
                drafts = resp["data"]["draft_words"]
                st.session_state[f"nl_draft_{unit_id}"] = drafts
                st.success(f"解析完成，识别到 {len(drafts)} 个词条")
            else:
                st.error(resp["message"])

    nl_draft_key = f"nl_draft_{unit_id}"
    if nl_draft_key in st.session_state:
        drafts = st.session_state[nl_draft_key]
        if not drafts:
            st.info("未识别到有效词条")
        else:
            st.subheader("📝 解析结果（可编辑）")
            confirmed = []
            for i, w in enumerate(drafts):
                col1, col2, col3 = st.columns([3, 3, 1])
                with col1:
                    en = st.text_input("英文", w["english"], key=f"nl_en_{i}")
                with col2:
                    cn = st.text_input("中文", w["chinese"], key=f"nl_cn_{i}")
                with col3:
                    tp = st.selectbox(
                        "类型", ["word", "sentence"],
                        index=0 if w["type"] == "word" else 1,
                        key=f"nl_tp_{i}",
                    )
                confirmed.append({"english": en, "chinese": cn, "type": tp})

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 确认并保存"):
                    resp = client.batch_create_words(unit_id, confirmed)
                    if resp["code"] == 200:
                        st.success(f"保存成功！新增 {resp['data']['created_count']} 个单词")
                        del st.session_state[nl_draft_key]
                        st.rerun()
                    else:
                        st.error(resp["message"])
            with c2:
                if st.button("🗑️ 放弃"):
                    del st.session_state[nl_draft_key]
                    st.rerun()

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
    col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 2, 1])
    with col1:
        st.markdown(f"**{w['english']}**")
    with col2:
        st.markdown(w["chinese"])
    with col3:
        mastery = w.get("mastery")
        level = mastery["level"] if mastery else "unlearned"
        color, label = MASTERY_COLORS.get(level, ("gray", level))
        st.badge(label, color=color)
    with col4:
        current_tags = w.get("tags", [])
        tag_emojis = " ".join(k.split()[0] for k, v in TAG_OPTIONS.items() if v in current_tags)
        with st.popover(tag_emojis or "🏷️"):
            selected_labels = [k for k, v in TAG_OPTIONS.items() if v in current_tags]
            new_tags = st.multiselect(
                "标签", list(TAG_OPTIONS.keys()),
                default=selected_labels, key=f"tags_{w['id']}",
            )
            if set(new_tags) != set(selected_labels):
                tag_values = [TAG_OPTIONS[t] for t in new_tags]
                client.set_tags(w["id"], tag_values)
    with col5:
        if st.button("🗑️", key=f"del_w_{w['id']}"):
            client.delete_word(w["id"])
            st.rerun()
