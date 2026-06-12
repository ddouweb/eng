import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from api_client import client

st.set_page_config(page_title="家庭英语学习", page_icon="📚", layout="wide")

# ── 登录认证 ───────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None

# 尝试从 session_state 恢复 token 到 client 模块
if st.session_state.token and client.get_token() is None:
    client.set_token(st.session_state.token)

if not st.session_state.token:
    st.title("📚 家庭英语学习")
    st.subheader("请登录")
    with st.form("login"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录")
        if submitted:
            if not username or not password:
                st.warning("请输入用户名和密码")
            else:
                resp = client.login(username, password)
                if resp["code"] == 200:
                    st.session_state.token = client.get_token()
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error(resp.get("message", "用户名或密码错误"))
    st.stop()

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

# AI 设置
st.sidebar.markdown("### 🤖 AI 设置")

if "ai_provider" not in st.session_state:
    st.session_state.ai_provider = "glm"
if "ai_api_key" not in st.session_state:
    st.session_state.ai_api_key = ""

provider = st.sidebar.selectbox(
    "AI 模型", ["glm", "claude", "deepseek"],
    index=["glm", "claude", "deepseek"].index(st.session_state.ai_provider),
)
if provider != st.session_state.ai_provider:
    st.session_state.ai_provider = provider

api_key = st.sidebar.text_input(
    "API Key", value=st.session_state.ai_api_key,
    type="password", placeholder="sk-...",
)
if api_key != st.session_state.ai_api_key:
    st.session_state.ai_api_key = api_key

if st.session_state.ai_api_key:
    st.sidebar.caption(f"✅ 已配置 {st.session_state.ai_provider}")
else:
    st.sidebar.caption("⚠️ 未配置 API Key，AI 功能不可用")

# 退出登录
st.sidebar.markdown("---")
if st.sidebar.button("🚪 退出登录"):
    client.set_token(None)
    st.session_state.token = None
    st.rerun()
