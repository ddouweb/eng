import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

from api_client import client
from auth import require_auth, clear_auth_cookie

st.set_page_config(page_title="家庭英语学习", page_icon="📚", layout="wide")

# 统一登录态校验：未登录或 token 失效时渲染登录表单并 stop()
require_auth()

# ── 已登录 ─────────────────────────────────────────────
st.title("📚 Family English Coach")
st.markdown("上传教材图片 → 自动生成单词库 → 练习 → 追踪掌握进度")

# 用户切换
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

# 退出登录
st.sidebar.markdown("---")
if st.sidebar.button("🚪 退出登录"):
    client.set_token(None)
    st.session_state.token = None
    st.session_state.pop("_prac_units", None)
    clear_auth_cookie()
    st.rerun()
