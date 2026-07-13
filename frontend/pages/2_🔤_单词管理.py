import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from api_client import client
from auth import require_auth
from components.phonetics import phonetic


def _json_for_script(obj):
    """序列化 JSON 并转义 < > & 与 U+2028/2029，安全嵌入 <script>。

    词库 english/chinese 是用户可控文本（手填 + AI 解析粘贴内容），
    json.dumps 默认不转义这些字符；若某词条含 ``</script>`` 字面量，
    会提前闭合脚本块（播放器整段失效，同源 iframe 下还可能执行注入脚本）。
    转义后 HTML 解析器不再将其当作脚本结束，JS 解析字符串时仍能还原成原字符。
    """
    return (
        json.dumps(obj, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


require_auth()

# 只读浏览页：撑满宽度 + 表格占满剩余高度（表格内部虚拟滚动）；不动 padding-top
st.markdown(
    """
    <style>
    /* stMain(外层) 与 block-container(内层) 嵌套，不能同一选择器同设 padding-top（会叠成 8rem）。
       外层归零，内层单层垫 0 清掉默认顶部留白。 */
    section[data-testid="stMain"] {
        padding-top: 0 !important;
    }
    .block-container {
        padding-top: 0 !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    /* 顶栏 sticky 到视口顶（盖住 header 带、与 Deploy 同高），留在主内容流里（侧边栏右边），
       不碰侧边栏导航；右侧留 250px 给 Deploy。 */
    .st-key-wm_topbar {
        position: sticky !important;
        top: 0 !important;
        z-index: 999999 !important;
        height: 3.75rem !important;
        margin: 0 250px 0 0 !important;
        padding: 0.5rem 1rem !important;
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


def _row_dict(w):
    if is_mobile:
        return {"英文": w["english"], "音标": phonetic(w["english"]), "中文": w["chinese"]}
    level = (w.get("mastery") or {}).get("level", "unlearned")
    return {
        "序号": w.get("seq"),
        "英文": w["english"],
        "音标": phonetic(w["english"]),
        "中文": w["chinese"],
        "状态": STATUS_LABEL.get(level, level),
    }


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


# ── 顶栏 sticky：Unit(窄 ~1/10) | 自动播放器(宽) | 刷新 ───
# Unit 选择器收窄，腾出的宽度全给播放器。播放器是纯客户端 JS：▶/⏮/⏭/推进
# 全在浏览器端，零 Streamlit rerun、零逐词请求（音频走浏览器缓存 + 后端磁盘缓存）。
with st.container(key="wm_topbar"):
    c_unit, c_player, c_ref = st.columns([1, 8, 1])
    with c_unit:
        selected = st.selectbox("选择 Unit", list(unit_options.keys()), label_visibility="collapsed")
    unit_id = unit_options[selected]

    # 全量加载本单元单词并缓存（虚拟滚动足以承载数千词；浏览/播放纯客户端，无 rerun）
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

    words = sorted(words, key=_seq_key)

    if total > 0:
        with c_player:
            _ap_data = [
                {"e": w["english"], "p": phonetic(w["english"]), "c": w["chinese"],
                 "u": client.get_tts_url(w["english"], "en")}
                for w in words
            ]
            components.html(
                """<div style="display:flex;align-items:center;gap:6px;padding:2px 6px;font-family:-apple-system,Segoe UI,sans-serif;">
                  <button id="ap_p"  style="min-width:42px;height:30px;font-size:15px;cursor:pointer;border-radius:6px;border:1px solid #ccc;background:#f3f3f3;">▶</button>
                  <button id="ap_pv" style="height:30px;cursor:pointer;border-radius:6px;border:1px solid #ccc;background:#f3f3f3;">⏮</button>
                  <button id="ap_nx" style="height:30px;cursor:pointer;border-radius:6px;border:1px solid #ccc;background:#f3f3f3;">⏭</button>
                  <select id="ap_sp" style="height:30px;font-size:13px;border-radius:6px;border:1px solid #ccc;">
                    <option value="0.8">0.8×</option><option value="1" selected>1×</option>
                    <option value="1.25">1.25×</option><option value="1.5">1.5×</option>
                  </select>
                  <span id="ap_i" style="font-size:14px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">点 ▶ 开始连续播放发音（⏮⏭ 切换）</span>
                  <audio id="ap_a" preload="auto"></audio>
                </div>
                <script>
                (function () {
                  const W = __WORDS__;
                  const a = document.getElementById('ap_a'), info = document.getElementById('ap_i'), bp = document.getElementById('ap_p');
                  let i = 0, playing = false;
                  function esc(s) {
                    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
                      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
                    });
                  }
                  function show() {
                    const w = W[i] || {};
                    info.innerHTML = '<b>' + (i + 1) + '/' + W.length + '</b> &nbsp; ' + esc(w.e) +
                      (w.p ? ' <span style="color:#888">/' + esc(w.p) + '/</span>' : '') + ' &mdash; ' + esc(w.c);
                  }
                  function load(k) {
                    i = Math.max(0, Math.min(W.length - 1, k));
                    const w = W[i]; if (!w) return;
                    a.src = w.u; a.playbackRate = parseFloat(document.getElementById('ap_sp').value) || 1; show();
                  }
                  function play()  { a.play().catch(function () {}); playing = true;  bp.textContent = '⏸'; }
                  function pause() { a.pause();                       playing = false; bp.textContent = '▶'; }
                  a.addEventListener('ended', function () {
                    if (playing && i < W.length - 1) { load(i + 1); play(); } else { pause(); info.textContent = '播放完毕'; }
                  });
                  // 音频加载失败(后端 503/空体/解码失败)时 ended 不触发，靠 error 推进，避免连播卡死
                  a.addEventListener('error', function () {
                    if (playing && i < W.length - 1) {
                      info.textContent = '（第 ' + (i + 1) + ' 个音频加载失败，跳过…）';
                      setTimeout(function () { load(i + 1); play(); }, 500);
                    } else if (playing) {
                      pause(); info.textContent = '播放完毕（含加载失败的词）';
                    } else {
                      info.textContent = '（第 ' + (i + 1) + ' 个音频加载失败）';
                    }
                  });
                  bp.addEventListener('click', function () {
                    if (playing) { pause(); } else { if (!a.src) load(0); play(); }
                  });
                  document.getElementById('ap_pv').addEventListener('click', function () { load(i - 1); if (playing) play(); });
                  document.getElementById('ap_nx').addEventListener('click', function () { load(i + 1); if (playing) play(); });
                  document.getElementById('ap_sp').addEventListener('change', function () { a.playbackRate = parseFloat(this.value) || 1; });
                  show();
                })();
                </script>""".replace("__WORDS__", _json_for_script(_ap_data)),
                height=40,
            )
    with c_ref:
        if st.button("🔄", help="重新加载本单元单词"):
            st.session_state.pop(cache_key, None)
            st.rerun()

if total == 0:
    st.info("这个 Unit 还没有单词。")
    st.stop()

if len(words) < total:
    st.warning(f"本单元共 {total} 词，单次最多加载 {len(words)} 词（后端上限 5000），未全部显示。")

# ── 只读浏览表（滚动浏览；发音由顶栏 JS 播放器控制）──────
df = pd.DataFrame([_row_dict(w) for w in words])
if not is_mobile:
    df["序号"] = pd.to_numeric(df["序号"], errors="coerce").astype("Int64")
st.dataframe(
    df, column_config=_col_cfg, hide_index=True, use_container_width=True,
    key=f"browse_{unit_id}",
)
