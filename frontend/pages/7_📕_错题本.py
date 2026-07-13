"""错题本页面：列出、移除、清空错题。

数据来源：练习中答错的题自动加入；本页只做展示与手动管理。
答对错题本中的词不会自动移除 —— 必须在这里手动点击「移除」。
"""
import json

import streamlit as st
import streamlit.components.v1 as components
from api_client import client
from auth import require_auth
from components.phonetics import phonetic

require_auth()

st.title("📕 错题本")
st.caption("练习中答错的题会自动加入。答对不会自动移除，需在此手动管理。")

member_id = st.session_state.get("member_id", 1)

# 顶部摘要 + 清空
cnt_resp = client.count_wrong_book(member_id=member_id)
if cnt_resp["code"] != 200:
    st.error(cnt_resp["message"])
    st.stop()
total = cnt_resp["data"]["total"]

col_summary, col_clear = st.columns([5, 1])
with col_summary:
    st.metric("错题总数", total)
with col_clear:
    if total > 0:
        confirm_flag = st.session_state.get("_wb_confirm_clear", False)
        label = "⚠️ 再点一次确认" if confirm_flag else "🗑️ 清空错题本"
        if st.button(label, use_container_width=True, type="primary" if confirm_flag else "secondary"):
            if confirm_flag:
                r = client.clear_wrong_book(member_id=member_id)
                st.session_state["_wb_confirm_clear"] = False
                if r["code"] == 200:
                    st.success(f"已清空 {r['data']['removed']} 条")
                    st.rerun()
                else:
                    st.error(r["message"])
            else:
                st.session_state["_wb_confirm_clear"] = True
                st.rerun()

if total == 0:
    st.info("错题本为空。在「练习」中答错的题会自动加入。")
    st.stop()

st.divider()

# 分页参数
PAGE_SIZE = 50
if "_wb_page" not in st.session_state:
    st.session_state["_wb_page"] = 1
page = st.session_state["_wb_page"]

resp = client.list_wrong_book(member_id=member_id, page=page, page_size=PAGE_SIZE)
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

data = resp["data"]
items = data["items"]
total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

st.caption(f"第 {page} / {total_pages} 页 · 每页 {PAGE_SIZE} 条")

MASTERY_EMOJI = {
    "unlearned": "⚪",
    "learning": "🟠",
    "familiar": "🔵",
    "permanent": "🟢",
}
MASTERY_LABEL = {
    "unlearned": "未学习",
    "learning": "学习中",
    "familiar": "熟悉",
    "permanent": "永久",
}

for it in items:
    wid = it["word_id"]
    with st.container(border=True):
        col_main, col_play, col_btn = st.columns([7, 1, 1])
        with col_main:
            mlevel = it.get("mastery_level") or "unlearned"
            icon = MASTERY_EMOJI.get(mlevel, "⚪")
            phon = phonetic(it["english"])
            ipa_md = f"　/{phon}/" if phon else ""
            st.markdown(f"### {it['english']}{ipa_md}")
            st.caption(
                f"中文：{it['chinese']}　·　"
                f"Unit：{it.get('unit_title') or '-'}　·　"
                f"掌握 {icon} {MASTERY_LABEL.get(mlevel, '未学习')}　·　"
                f"🔥 错题本中累计错 {it.get('wrong_count', 0)} 次　·　"
                f"加入于 {(it.get('added_at') or '')[:16]}"
            )
        with col_play:
            # 纯 JS 播放（components.html iframe 内）：点击不触发 Streamlit rerun，
            # 也就不会重拉错题列表 API；audio preload=none，点前不请求。
            _url = client.get_tts_url(it["english"], "en")
            components.html(
                """<button type="button" aria-label="播放发音" style="width:100%;height:30px;font-size:15px;cursor:pointer;border-radius:6px;border:1px solid #ccc;background:#f3f3f3;">🔊</button>
                <audio preload="none"></audio>
                <script>
                  (function () {
                    var a = document.querySelector('audio');
                    a.src = __URL__;
                    document.querySelector('button').addEventListener('click', function () { a.play(); });
                  })();
                </script>""".replace("__URL__", json.dumps(_url)),
                height=32,
            )
        with col_btn:
            if st.button("移除", key=f"rm_{wid}", use_container_width=True):
                r = client.remove_wrong_word(wid, member_id=member_id)
                if r["code"] == 200:
                    st.toast(f"已移除 {it['english']}")
                    # 若当前页删完，回到上一页避免空页
                    if len(items) == 1 and page > 1:
                        st.session_state["_wb_page"] = page - 1
                    st.rerun()
                else:
                    st.error(r["message"])

st.divider()
nav_l, nav_info, nav_r = st.columns([1, 6, 1])
with nav_l:
    if st.button("⬅️ 上一页", use_container_width=True, disabled=(page <= 1)):
        st.session_state["_wb_page"] = page - 1
        st.rerun()
with nav_info:
    st.caption(f"第 {page} / {total_pages} 页")
with nav_r:
    if st.button("➡️ 下一页", use_container_width=True, disabled=(page >= total_pages)):
        st.session_state["_wb_page"] = page + 1
        st.rerun()
