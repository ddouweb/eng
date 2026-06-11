import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(page_title="家庭英语学习", page_icon="📚", layout="wide")
st.title("📚 Family English Coach")
st.markdown("上传教材图片 → 自动生成单词库 → 练习 → 追踪掌握进度")

# ── 用户切换 ───────────────────────────────────────────
if "member_id" not in st.session_state:
    st.session_state.member_id = 1

MEMBERS = [
    {"id": 1, "name": "默认用户"},
    {"id": 2, "name": "家庭成员 2"},
    {"id": 3, "name": "家庭成员 3"},
]

st.sidebar.markdown("### 👤 用户")
member_names = [m["name"] for m in MEMBERS]
current_idx = next((i for i, m in enumerate(MEMBERS) if m["id"] == st.session_state.member_id), 0)

selected = st.sidebar.selectbox("选择用户", member_names, index=current_idx)
new_id = MEMBERS[member_names.index(selected)]["id"]
if new_id != st.session_state.member_id:
    st.session_state.member_id = new_id
    st.rerun()
