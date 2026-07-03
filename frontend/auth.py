"""统一登录态校验。

Streamlit 多页面应用中，pages/ 下每个文件是独立脚本，用户可以直接访问任何 page URL，
不会经过 app.py。所以登录态检查必须放在每个 page 开头调用 require_auth()，
否则未登录用户能直接进入 page，触发 API 401 死循环或看到"加载失败"。

用法:
    # pages/xxx.py
    from auth import require_auth
    require_auth()
    st.header(...)  # 后续业务代码
"""
import streamlit as st
import streamlit.components.v1 as components

from api_client import client

COOKIE_NAME = "auth_token"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 天


def set_auth_cookie(token: str):
    components.html(
        f'<script>document.cookie="{COOKIE_NAME}={token}; path=/; '
        f'max-age={COOKIE_MAX_AGE}; SameSite=Lax";</script>',
        height=0,
    )


def clear_auth_cookie():
    components.html(
        f'<script>document.cookie="{COOKIE_NAME}=; path=/; '
        f'max-age=0; SameSite=Lax";</script>',
        height=0,
    )


def _restore_from_cookie():
    """首次进入 page 时从浏览器 cookie 恢复 token 到 session_state。"""
    if "token" not in st.session_state:
        cookie_token = st.context.cookies.get(COOKIE_NAME)
        if cookie_token:
            st.session_state.token = cookie_token
            client.set_token(cookie_token)
        else:
            st.session_state.token = None
    elif st.session_state.token and client.get_token() is None:
        client.set_token(st.session_state.token)


def _render_login_form():
    """未登录时渲染登录表单；登录成功后写入 token 并 rerun。"""
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
                    set_auth_cookie(new_token)
                    # 清除可能由未登录态访问页面留下的脏缓存
                    st.session_state.pop("_prac_units", None)
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error(resp.get("message", "用户名或密码错误"))


def require_auth():
    """每个 page 开头调用。未登录或 token 失效时渲染登录表单并停止后续渲染。"""
    _restore_from_cookie()

    # API 调用返回 401 时 client 会清掉 token 并设置标志位；
    # 这里在每次进入页面时检测到，立即清登录态并 rerun 到登录表单
    if client.is_auth_invalid():
        client.clear_auth_invalid()
        client.set_token(None)
        st.session_state.token = None
        st.session_state.pop("_prac_units", None)
        clear_auth_cookie()
        st.rerun()

    if not st.session_state.token:
        _render_login_form()
        st.stop()
