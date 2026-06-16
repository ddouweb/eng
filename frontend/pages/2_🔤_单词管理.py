import pandas as pd
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
        with st.spinner("AI 正在解析文本..."):
            resp = client.parse_words(nl_text.strip())
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

# ── 单词列表（统一编辑表格）─────────────────────────
resp = client.list_words(unit_id, page_size=200)
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

words = resp["data"]["items"]
if not words:
    st.info("这个 Unit 还没有单词。")
    st.stop()

STATUS_LABEL = {
    "unlearned": "🔴 未学习",
    "learning": "🟠 学习中",
    "familiar": "🔵 熟悉",
    "permanent": "🟢 永久",
}

# 构建 DataFrame：仅编辑文字，状态只读展示
rows = []
for w in words:
    level = (w.get("mastery") or {}).get("level", "unlearned")
    rows.append({
        "ID": w["id"],
        "英文": w["english"],
        "中文": w["chinese"],
        "状态": STATUS_LABEL.get(level, level),
    })
df = pd.DataFrame(rows)

st.caption(f"共 {len(words)} 个单词 · 双击编辑英文/中文 · 状态由练习自动更新 · 点击保存生效")

edited = st.data_editor(
    df,
    column_config={
        "ID": st.column_config.NumberColumn(disabled=True, width="small"),
        "英文": st.column_config.TextColumn(width="medium"),
        "中文": st.column_config.TextColumn(width="medium"),
        "状态": st.column_config.TextColumn(disabled=True, width="small"),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    key=f"editor_{unit_id}",
)

if st.button("💾 保存所有修改", type="primary"):
    changed = 0
    for orig, row in zip(words, edited.itertuples()):
        if orig["english"] != row.英文 or orig["chinese"] != row.中文:
            r = client.update_word(orig["id"], english=row.英文, chinese=row.中文)
            if r["code"] == 200:
                changed += 1
    if changed:
        st.success(f"已更新 {changed} 个单词")
        st.rerun()
    else:
        st.info("没有检测到修改")
