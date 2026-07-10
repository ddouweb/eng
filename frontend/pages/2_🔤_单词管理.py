import re

import pandas as pd
import streamlit as st
from api_client import client
from auth import require_auth
from components.phonetics import phonetic

require_auth()

# 只读浏览页：撑满宽度 + 表格占满剩余高度（表格内部虚拟滚动）；不动 padding-top
st.markdown(
    """
    <style>
    /* stMain(外层) 与 block-container(内层) 是嵌套关系，
       不能用同一选择器同时设 padding-top，否则两层叠加成 8rem。
       外层归零，只让内层单层垫 4rem 刚好清掉固定 header(3.75rem)。 */
    section[data-testid="stMain"] {
        padding-top: 0 !important;
    }
    .block-container {
        padding-top: 0 !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    /* 工具条 sticky 到视口顶（盖住 header 带、与 Deploy 同高），但它留在主内容流里
       （侧边栏右边），所以不碰侧边栏导航；右侧留 250px 给 Deploy。 */
    .st-key-wm_topbar {
        position: sticky !important;
        top: 0 !important;
        z-index: 999999 !important;
        height: 3.75rem !important;
        margin: 0 250px 0 0 !important;
        padding: 0.6rem 1rem !important;
        background: var(--background-color, #ffffff) !important;
    }
    div[data-testid="stDataFrame"] {
        height: calc(100vh - 110px) !important;
        min-height: 420px;
        width: 100% !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {
        height: 100% !important;
        width: 100% !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _is_mobile() -> bool:
    try:
        ua = st.context.headers.get("User-Agent", "")
    except Exception:
        return False
    return bool(re.search(r"Mobile|Android|iPhone|iPad|iPod", ua, re.I))


is_mobile = _is_mobile()

# ── Unit 列表 ───────────────────────────────────────────
resp = client.list_all_units()
if resp["code"] != 200:
    st.error(f"加载失败: {resp['message']}")
    st.stop()
units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，请先到 Units 页面创建。")
    st.stop()
unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}

# 顶栏 sticky 到视口顶：用 st.container(key=) 拿到 .st-key-wm_topbar 类做定位
with st.container(key="wm_topbar"):
    c_unit, c_info, c_ref = st.columns([7, 3, 1])
    with c_unit:
        selected = st.selectbox("选择 Unit", list(unit_options.keys()), label_visibility="collapsed")
    unit_id = unit_options[selected]

    # 全量加载本单元单词并缓存到 session_state：表格虚拟滚动足以承载数千词，
    # 缓存后点行播放的 rerun 不会反复请求后端。
    cache_key = f"_wm_all_{unit_id}"
    words = st.session_state.get(cache_key)
    if words is None:
        resp = client.list_words(unit_id, page=1, page_size=5000)
        if resp["code"] != 200:
            st.error(resp["message"])
            st.stop()
        words = resp["data"]["items"]
        total = resp["data"]["total"]
        st.session_state[cache_key] = words
        st.session_state[cache_key + "_total"] = total
    else:
        total = st.session_state.get(cache_key + "_total", len(words))

    with c_info:
        if len(words) >= total:
            st.caption(f"共 {total} 词（已全部加载，滚动浏览）")
        else:
            st.caption(f"共 {total} 词（仅加载前 {len(words)}）")
    with c_ref:
        if st.button("🔄", help="重新加载本单元单词"):
            st.session_state.pop(cache_key, None)
            st.rerun()

if total == 0:
    st.info("这个 Unit 还没有单词。")
    st.stop()

if len(words) < total:
    st.warning(f"本单元共 {total} 词，单次最多加载 {len(words)} 词（后端上限 5000），未全部显示。")


def _seq_key(w):
    s = w.get("seq")
    if s is None:
        return (True, 0)
    try:
        return (False, int(s))
    except (TypeError, ValueError):
        return (True, 0)


STATUS_LABEL = {
    "unlearned": "⚪ 未学习",
    "learning": "🟠 学习中",
    "familiar": "🔵 熟悉",
    "permanent": "🟢 永久",
}

words = sorted(words, key=_seq_key)

# ── 只读浏览表（点行 → 上方播放发音）────────────────────
rows = []
for w in words:
    if is_mobile:
        rows.append({"英文": w["english"], "音标": phonetic(w["english"]), "中文": w["chinese"]})
    else:
        level = (w.get("mastery") or {}).get("level", "unlearned")
        rows.append({
            "序号": w.get("seq"),
            "英文": w["english"],
            "音标": phonetic(w["english"]),
            "中文": w["chinese"],
            "状态": STATUS_LABEL.get(level, level),
        })
df = pd.DataFrame(rows)
if not is_mobile:
    df["序号"] = pd.to_numeric(df["序号"], errors="coerce").astype("Int64")

if is_mobile:
    _col_cfg = {
        "英文": st.column_config.TextColumn(width="small"),
        "音标": st.column_config.TextColumn(width="medium"),
        "中文": st.column_config.TextColumn(width="medium"),
    }
else:
    _col_cfg = {
        "序号": st.column_config.NumberColumn(width="small"),
        "英文": st.column_config.TextColumn(width="medium"),
        "音标": st.column_config.TextColumn(width="medium"),
        "中文": st.column_config.TextColumn(width="large"),
        "状态": st.column_config.TextColumn(width="small"),
    }

# 播放器占位（渲染在表格上方，点行后立即可见）
player_ph = st.empty()

# st.dataframe 支持行选择；返回 {"selection": {"rows": [行号], ...}}，行号为原始 df 位置（排序后仍对齐 words）
browse_sel = st.dataframe(
    df,
    column_config=_col_cfg,
    hide_index=True,
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
    key=f"browse_{unit_id}",
)
sel_rows = (browse_sel or {}).get("selection", {}).get("rows", [])

with player_ph.container():
    if sel_rows and 0 <= sel_rows[-1] < len(words):
        w = words[sel_rows[-1]]
        phon = phonetic(w["english"])
        c_w, c_a = st.columns([2, 3])
        c_w.markdown(f"### 🔊 {w['english']}　{f'/{phon}/' if phon else ''}")
        c_a.audio(client.get_tts_url(w["english"], "en"), format="audio/mpeg", autoplay=True)
    else:
        st.caption("👆 点击表格中任一行 → 播放该单词发音")
