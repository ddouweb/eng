import streamlit as st
from api_client import client
from auth import require_auth

require_auth()
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
                # 失效练习页的 Unit 缓存，让新建 Unit 立即可见
                st.session_state.pop("_prac_units", None)
                st.rerun()
            else:
                st.error(resp["message"])

# ── Unit 列表 ────────────────────────────────────────
resp = client.list_all_units()
if resp["code"] != 200:
    st.error(f"加载失败: {resp['message']}")
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，点击上方「创建新 Unit」开始。")
    st.stop()

for unit in units:
    uid = unit["id"]
    pending = st.session_state.get("pending_delete_unit") == uid
    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.markdown(f"**{unit['title']}**")
        with col2:
            st.caption(f"序号: {unit['sequence']} | 单词数: {unit.get('word_count', 0)}")
        with col3:
            if pending:
                if st.button("取消", key=f"cancel_del_{uid}", use_container_width=True):
                    st.session_state.pop("pending_delete_unit", None)
                    st.rerun()
            elif st.button("🗑️", key=f"del_unit_{uid}"):
                # 两步确认：点一次进入待删状态，需二次确认才真正删除。
                # 删 Unit 会级联删除其下全部单词及关联掌握度/错题记录，不可恢复。
                st.session_state["pending_delete_unit"] = uid
                st.rerun()
        if pending:
            st.warning(
                f"⚠️ 将永久删除「{unit['title']}」及其 {unit.get('word_count', 0)} 个单词"
                "（含相关掌握度与错题记录），此操作不可恢复。"
            )
            cc1, _ = st.columns([1, 4])
            if cc1.button("✅ 确认删除", key=f"confirm_del_{uid}", type="primary"):
                del_resp = client.delete_unit(uid)
                st.session_state.pop("pending_delete_unit", None)
                if del_resp["code"] == 200:
                    st.success("已删除")
                    # 失效练习页的 Unit 缓存，避免引用已删除的 Unit
                    st.session_state.pop("_prac_units", None)
                    st.rerun()
                else:
                    st.error(del_resp["message"])

st.info("💡 单词请到「单词管理」页面手动或通过 AI 文本解析添加。")
