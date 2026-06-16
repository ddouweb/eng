import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import streamlit.components.v1 as components
from api_client import client

st.set_page_config(page_title="家庭英语学习", page_icon="📚", layout="wide")

COOKIE_NAME = "auth_token"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 天


def _set_auth_cookie(token: str):
    components.html(
        f'<script>document.cookie="{COOKIE_NAME}={token}; path=/; '
        f'max-age={COOKIE_MAX_AGE}; SameSite=Lax";</script>',
        height=0,
    )


def _clear_auth_cookie():
    components.html(
        f'<script>document.cookie="{COOKIE_NAME}=; path=/; '
        f'max-age=0; SameSite=Lax";</script>',
        height=0,
    )


# ── 登录认证 ───────────────────────────────────────────
# session_state 仅在单个 WebSocket 会话内存活；刷新页面/新标签页就会丢。
# 改为从浏览器 cookie 读取 token，刷新后自动恢复登录状态。
if "token" not in st.session_state:
    cookie_token = st.context.cookies.get(COOKIE_NAME)
    if cookie_token:
        st.session_state.token = cookie_token
        client.set_token(cookie_token)
    else:
        st.session_state.token = None
elif st.session_state.token and client.get_token() is None:
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
                    new_token = client.get_token()
                    st.session_state.token = new_token
                    _set_auth_cookie(new_token)
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

# 退出登录
st.sidebar.markdown("---")
if st.sidebar.button("🚪 退出登录"):
    client.set_token(None)
    st.session_state.token = None
    _clear_auth_cookie()
    st.rerun()
