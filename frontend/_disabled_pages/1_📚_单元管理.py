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

st.info("💡 单词请到「单词管理」页面手动或通过 AI 文本解析添加。")
