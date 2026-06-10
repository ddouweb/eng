import streamlit as st
from api_client import client

st.header("📚 单元管理")

# ── 创建新 Unit ──────────────────────────────────────
with st.expander("➕ 创建新 Unit"):
    title = st.text_input("Unit 标题", placeholder="Unit 1 - Hello!")
    sequence = st.number_input("序号", min_value=1, value=1, step=1)
    if st.button("创建"):
        if not title.strip():
            st.error("请输入标题")
        else:
            resp = client.create_unit(title.strip(), sequence)
            if resp["code"] == 200:
                st.success(f"Unit 创建成功！ID={resp['data']['id']}")
                st.rerun()
            else:
                st.error(resp["message"])

# ── Unit 列表 ────────────────────────────────────────
resp = client.list_units()
if resp["code"] != 200:
    st.error(f"加载失败: {resp['message']}")
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，点击上方「创建新 Unit」开始。")
    st.stop()

for unit in units:
    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.markdown(f"**{unit['title']}**")
        with col2:
            st.caption(f"序号: {unit['sequence']} | 单词数: {unit.get('word_count', 0)}")
        with col3:
            if st.button("🗑️", key=f"del_unit_{unit['id']}"):
                del_resp = client.delete_unit(unit["id"])
                if del_resp["code"] == 200:
                    st.success("已删除")
                    st.rerun()
                else:
                    st.error(del_resp["message"])

# ── 上传图片到 Unit ──────────────────────────────────
st.divider()
st.subheader("📷 上传教材图片")
unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}
selected = st.selectbox("选择 Unit", list(unit_options.keys()))
unit_id = unit_options[selected]

uploaded = st.file_uploader("选择图片", type=["jpg", "jpeg", "png", "webp"], key="upload_img")
if uploaded and st.button("上传并解析"):
    with st.spinner("AI 正在解析图片..."):
        resp = client.upload_image(unit_id, uploaded.read(), uploaded.name)
    if resp["code"] == 200:
        drafts = resp["data"]["draft_words"]
        st.session_state[f"ocr_draft_{unit_id}"] = drafts
        st.success(f"解析完成，识别到 {len(drafts)} 个单词")
    else:
        st.error(resp["message"])

# ── OCR 草稿确认 ─────────────────────────────────────
draft_key = f"ocr_draft_{unit_id}"
if draft_key in st.session_state:
    st.subheader("📝 解析结果（可编辑）")
    drafts = st.session_state[draft_key]
    if not drafts:
        st.info("无识别结果")
    else:
        confirmed = []
        for i, w in enumerate(drafts):
            col1, col2, col3 = st.columns([3, 3, 1])
            with col1:
                en = st.text_input("英文", w["english"], key=f"draft_en_{i}")
            with col2:
                cn = st.text_input("中文", w["chinese"], key=f"draft_cn_{i}")
            with col3:
                tp = st.selectbox("类型", ["word", "sentence"], index=0 if w["type"] == "word" else 1, key=f"draft_tp_{i}")
            confirmed.append({"english": en, "chinese": cn, "type": tp})

        if st.button("✅ 确认并保存"):
            resp = client.confirm_ocr(unit_id, confirmed)
            if resp["code"] == 200:
                st.success(f"保存成功！新增 {resp['data']['created_count']} 个单词")
                del st.session_state[draft_key]
                st.rerun()
            else:
                st.error(resp["message"])
