import pandas as pd
import streamlit as st
from api_client import client

# 隐藏整条顶部 header（含右上角三个点主菜单）让内容顶格；
# 内容区顶到视口左右边缘让表格横向真正占满（wide 布局默认有 max-width + 左右 padding 会把表格收窄、
# 还可能因收窄后宽度 < 列宽之和而出现横向滚动条）；
# 表格撑满视口剩余高度
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    .block-container, section[data-testid="stMain"] {
        padding-top: 0.5rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    div[data-testid="stDataFrame"] {
        height: calc(100vh - 180px) !important;
        min-height: 420px;
        width: 100% !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {
        height: 100% !important;
        width: 100% !important;
    }
    /* 禁用列头点击排序：默认即按序号升序（行顺序）显示，切换单元也自动升序，无需手动点 */
    div[data-testid="stDataFrame"] [role="columnheader"],
    div[data-testid="stDataFrame"] th,
    div[data-testid="stDataFrame"] [data-testid*="column-header"] {
        pointer-events: none !important;
        cursor: default !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 选择 Unit（顶格；标签与下拉框同一行）──────────────
resp = client.list_units(page_size=100)
if resp["code"] != 200:
    st.error(f"加载失败: {resp['message']}")
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，请先到 Units 页面创建。")
    st.stop()

unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}
_label_col, _select_col = st.columns([1, 5])
with _label_col:
    st.markdown(
        '<div style="font-size:16px; font-weight:600; padding-top:8px;">选择 Unit</div>',
        unsafe_allow_html=True,
    )
with _select_col:
    selected = st.selectbox(
        "选择 Unit",
        list(unit_options.keys()),
        label_visibility="collapsed",
    )
unit_id = unit_options[selected]

# ── 单词列表（统一编辑表格；按序号升序，撑满页面）─────────
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

# 按 seq 数字升序兜底排序（None 排末尾）；words 与 df 必须同序，保存时才能按行对齐
def _seq_key(w):
    s = w.get("seq")
    if s is None:
        return (True, 0)
    try:
        return (False, int(s))   # 显式转 int，避免字符串字典序（1,10,11 而非 1,2,...10）
    except (TypeError, ValueError):
        return (True, 0)


words = sorted(words, key=_seq_key)

rows = []
for w in words:
    level = (w.get("mastery") or {}).get("level", "unlearned")
    rows.append({
        "序号": w.get("seq"),
        "英文": w["english"],
        "中文": w["chinese"],
        "状态": STATUS_LABEL.get(level, level),
    })
df = pd.DataFrame(rows)
# 「序号」强制为可空整数类型，避免被当成字符串排序（出现 1,10,11 而非 1,2,...10）
df["序号"] = pd.to_numeric(df["序号"], errors="coerce").astype("Int64")

edited = st.data_editor(
    df,
    column_config={
        "序号": st.column_config.NumberColumn(width="small", step=1),
        "英文": st.column_config.TextColumn(width="large"),
        "中文": st.column_config.TextColumn(width="large"),
        "状态": st.column_config.TextColumn(disabled=True, width="small"),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    height=600,
    key=f"editor_{unit_id}",
)

if st.button("💾 保存所有修改", type="primary"):
    changed = 0
    for orig, row in zip(words, edited.itertuples()):
        seq_val = int(row.序号) if pd.notna(row.序号) else None
        if (orig["english"] != row.英文 or orig["chinese"] != row.中文
                or orig.get("seq") != seq_val):
            r = client.update_word(
                orig["id"], english=row.英文, chinese=row.中文, seq=seq_val
            )
            if r["code"] == 200:
                changed += 1
    if changed:
        st.success(f"已更新 {changed} 个单词")
        st.rerun()
    else:
        st.info("没有检测到修改")

# ── 手动添加单词（放在最后，默认折叠）──────────────────
with st.expander("➕ 手动添加单词", expanded=False):
    words_text = st.text_area("每行一个：英文,中文", placeholder="hello,你好\ngood morning,早上好")
    if st.button("批量添加"):
        lines = [l.strip() for l in words_text.strip().split("\n") if l.strip()]
        new_words = []
        for line in lines:
            parts = line.split(",", 1)
            if len(parts) == 2:
                new_words.append({"english": parts[0].strip(), "chinese": parts[1].strip(), "type": "word"})
        if new_words:
            resp = client.batch_create_words(unit_id, new_words)
            if resp["code"] == 200:
                st.success(f"添加 {resp['data']['created_count']} 个单词")
                st.rerun()
            else:
                st.error(resp["message"])
