"""单词查询页：跨所有 Unit 搜已收录单词（关键词/标签/掌握度/Unit 过滤），定位它属于哪个 Unit。

每条结果带「音标 + ▶ 播放」。播放走 blob 缓存：首次 fetch→blob→缓存，再次播放零网络
（fetch 失败兜底直链，仍可播）。注：掌握度 emoji/label 此处第 3 份内联，未来可抽 components/mastery.py。
"""
import json

import streamlit as st
import streamlit.components.v1 as components
from api_client import client
from auth import require_auth
from components.phonetics import phonetic

require_auth()

st.title("📖 单词查询")
st.caption("🔎 跨所有 Unit 搜已收录单词，按关键词/标签/掌握度/Unit 过滤，定位它属于哪个 Unit。每条都带音标与播放，重复播放不重复请求。")

member_id = st.session_state.get("member_id", 1)

TAG_OPTIONS = {
    "（不限）": None,
    "⭐ 收藏 favorite": "favorite",
    "🔥 高频 high_freq": "high_freq",
    "📚 考点 exam_focus": "exam_focus",
    "❌ 排除 excluded": "excluded",
    "✅ 已记 memorized": "memorized",
}
LEVEL_OPTIONS = {
    "（不限）": None,
    "⚪ 未学习 unlearned": "unlearned",
    "🟠 学习中 learning": "learning",
    "🔵 熟悉 familiar": "familiar",
    "🟢 永久 permanent": "permanent",
}
MASTERY_EMOJI = {"unlearned": "⚪", "learning": "🟠", "familiar": "🔵", "permanent": "🟢"}
MASTERY_LABEL = {"unlearned": "未学习", "learning": "学习中", "familiar": "熟悉", "permanent": "永久"}

PAGE_SIZE = 50

# Unit 列表用于「按 Unit 过滤」，加载一次复用。
_units_resp = client.list_all_units()
_units = _units_resp["data"]["items"] if _units_resp.get("code") == 200 else []
UNIT_OPTIONS = {"（不限）": None}
UNIT_OPTIONS.update({f"{u['title']} (ID:{u['id']})": u["id"] for u in _units})


def _play_button(text: str):
    """单个 ▶ 播放按钮：blob 缓存，再次播放零网络；fetch 失败兜底直链（仍可播）。

    XSS 不变式：TTS URL 经 ``client.get_tts_url`` 内部 ``quote()`` 处理，不可能含 <> 或引号，
    故用 ``json.dumps`` 嵌入 JS 是安全的 —— 本函数只接受 TTS URL；任何用户可控文本若需嵌入
    ``<script>`` 必须改用 ``_json_for_script``（见 单词管理页）。
    """
    url = client.get_tts_url(text, "en")
    html = """
    <div style="display:flex;justify-content:center;">
      <button type="button" aria-label="播放发音" style="width:100%;min-width:42px;height:34px;font-size:16px;cursor:pointer;border-radius:6px;border:1px solid #ccc;background:#f3f3f3;">🔊</button>
    </div>
    <audio></audio>
    <script>
    (function () {
      var TTS_URL = __URL__;
      var a = document.querySelector('audio');
      var btn = document.querySelector('button');
      var blobUrl = null, pending = null, directUsed = false;
      function ensure() {
        if (blobUrl) return Promise.resolve();
        if (!pending) {
          // fetch 对 503/空体也会 resolve，必须校验 r.ok 与体积，否则会把 0 字节 blob 缓死、
          // 兜底直链永不触发。失败时 pending 归零，允许下次重试，并让点击走 catch 兜底。
          pending = fetch(TTS_URL).then(function (r) {
            if (!r.ok) throw new Error('http ' + r.status);
            return r.blob();
          }).then(function (b) {
            if (!b || b.size === 0) throw new Error('empty audio');
            blobUrl = URL.createObjectURL(b);
          }).catch(function (e) { pending = null; throw e; });
        }
        return pending;
      }
      btn.addEventListener('click', function () {
        if (blobUrl) { a.src = blobUrl; a.play(); return; }                      // 命中：零网络
        ensure().then(function () { a.src = blobUrl; a.play(); })                // 首次：取一次再缓存
                .catch(function () { if (!directUsed) { a.src = TTS_URL; directUsed = true; } a.play(); });  // 兜底直链
      });
    })();
    </script>
    """.replace("__URL__", json.dumps(url))
    components.html(html, height=38)


with st.form("wq_search"):
    q = st.text_input("关键词（英文或中文，模糊匹配）", key="wq_q")
    c1, c2, c3 = st.columns(3)
    tag_sel = c1.selectbox("标签", list(TAG_OPTIONS.keys()), key="wq_tag")
    level_sel = c2.selectbox("掌握程度", list(LEVEL_OPTIONS.keys()), key="wq_level")
    unit_sel = c3.selectbox("所在 Unit", list(UNIT_OPTIONS.keys()), key="wq_unit")
    submitted = st.form_submit_button("🔍 搜索", type="primary")

if submitted:
    st.session_state["_wq_submitted"] = True
    st.session_state["_wq_page"] = 1

if st.session_state.get("_wq_submitted"):
    page = st.session_state.get("_wq_page", 1)
    resp = client.search_words(
        q or None, member_id,
        tag=TAG_OPTIONS[tag_sel], level=LEVEL_OPTIONS[level_sel],
        unit_id=UNIT_OPTIONS[unit_sel], page=page, page_size=PAGE_SIZE,
    )
    if resp["code"] != 200:
        st.error(resp["message"])
        st.stop()
    data = resp["data"]
    items = data["items"]
    total = data["total"]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    st.caption(f"共 {total} 条　·　第 {page}/{total_pages} 页")
    if not items:
        st.info("没有匹配的单词。")
    else:
        units_hit = sorted({it.get("unit_title") for it in items if it.get("unit_title")})
        if units_hit:
            st.caption(f"命中 Unit：{', '.join(units_hit)}")
        for it in items:
            with st.container(border=True):
                cm, cp = st.columns([9, 1])
                with cm:
                    phon = phonetic(it["english"])
                    ipa = f"　/{phon}/" if phon else ""
                    lvl = (it.get("mastery") or {}).get("level")
                    icon = MASTERY_EMOJI.get(lvl, "⚪")
                    label = MASTERY_LABEL.get(lvl, "未学习")
                    tags = ", ".join(it.get("tags") or []) or "-"
                    st.markdown(f"**{it['english']}**{ipa}")
                    st.caption(
                        f"中文：{it['chinese']}　·　Unit：{it.get('unit_title') or '-'}　"
                        f"·　{icon} {label}　·　标签：{tags}"
                    )
                with cp:
                    _play_button(it["english"])
        nav_l, _, nav_r = st.columns([1, 6, 1])
        with nav_l:
            if st.button("⬅️ 上一页", disabled=(page <= 1), use_container_width=True):
                st.session_state["_wq_page"] = page - 1
                st.rerun()
        with nav_r:
            if st.button("➡️ 下一页", disabled=(page >= total_pages), use_container_width=True):
                st.session_state["_wq_page"] = page + 1
                st.rerun()
else:
    st.info("输入关键词或选择筛选条件后点「🔍 搜索」。")
