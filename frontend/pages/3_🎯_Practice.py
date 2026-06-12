import threading

import streamlit as st
from api_client import client

MODES = {
    "flashcard": "🃏 单词卡",
    "spelling": "✏️ 拼写",
    "choice": "🔘 选择题",
    "dictation": "🎧 听写",
}


def _bg_submit(session_id, word_id, is_correct, user_answer=None):
    threading.Thread(
        target=client.submit_answer,
        args=(session_id, word_id, is_correct),
        kwargs={"user_answer": user_answer},
        daemon=True,
    ).start()


st.header("🎯 练习")

# ── 状态初始化 ─────────────────────────────────────────
if "prac" not in st.session_state:
    st.session_state.prac = {
        "questions": [],
        "idx": 0,
        "session_id": None,
        "results": [],
        "mode": None,
        "unit_ids": [],
        "finished": False,
    }

p = st.session_state.prac
in_practice = bool(p["questions"]) and p["idx"] < len(p["questions"])
practice_done = bool(p["questions"]) and p["idx"] >= len(p["questions"])

# ── 配置区（仅练习未开始时显示）────────────────────────
if not in_practice and not practice_done:
    if "_prac_units" not in st.session_state:
        resp = client.list_units(page_size=100)
        st.session_state["_prac_units"] = resp["data"]["items"] if resp["code"] == 200 else []

    units = st.session_state["_prac_units"]
    if not units:
        st.info("还没有 Unit，请先添加单词。")
        st.stop()

    unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}
    selected_keys = st.multiselect("选择 Unit", list(unit_options.keys()))
    selected_ids = [unit_options[k] for k in selected_keys]

    mode = st.selectbox("练习模式", list(MODES.keys()), format_func=lambda x: MODES[x])
    count = st.slider("题目数量", 5, 30, 10)

    if st.button("🚀 开始练习", disabled=not selected_ids):
        member_id = st.session_state.get("member_id", 1)
        resp = client.start_practice(member_id=member_id, mode=mode, unit_ids=selected_ids, count=count)
        if resp["code"] == 200:
            p.update({
                "questions": resp["data"]["questions"],
                "session_id": resp["data"]["session_id"],
                "idx": 0,
                "results": [],
                "mode": mode,
                "unit_ids": selected_ids,
                "finished": False,
            })
            st.rerun()
        else:
            st.error(resp["message"])

# ── 练习进行中（本地状态 + 后台异步提交）────────────────
if in_practice:
    q = p["questions"][p["idx"]]
    sid = p["session_id"]
    total = len(p["questions"])
    st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")

    if p["mode"] == "flashcard":
        if "fc_show" not in st.session_state:
            st.session_state.fc_show = False
        st.markdown(f"### {q['english']}")
        if st.button("显示答案" if not st.session_state.fc_show else "隐藏答案"):
            st.session_state.fc_show = not st.session_state.fc_show
        if st.session_state.fc_show:
            st.info(f"**{q['chinese']}**")

        col_ok, col_fail = st.columns(2)
        with col_ok:
            if st.button("✅ 认识", use_container_width=True):
                _bg_submit(sid, q["word_id"], True)
                p["results"].append(True)
                p["idx"] += 1
                st.session_state.fc_show = False
                st.rerun()
        with col_fail:
            if st.button("❌ 不认识", use_container_width=True):
                _bg_submit(sid, q["word_id"], False, q["english"])
                p["results"].append(False)
                p["idx"] += 1
                st.session_state.fc_show = False
                st.rerun()

    elif p["mode"] == "spelling":
        from components.spelling_input import render as spelling
        answer = spelling(q["chinese"], q["word_id"])
        if answer is not None:
            correct = answer.lower() == q["english"].lower()
            if correct:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 错误，正确答案: **{q['english']}**")
            _bg_submit(sid, q["word_id"], correct, answer)
            p["results"].append(correct)
            p["idx"] += 1
            st.rerun()

    elif p["mode"] == "choice":
        options = q.get("options", [q["chinese"]])
        from components.choice_quiz import render as choice
        answer = choice(q["english"], options, q["chinese"], q["word_id"])
        if answer is not None:
            correct = answer == q["chinese"]
            if correct:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 错误，正确答案: **{q['chinese']}**")
            _bg_submit(sid, q["word_id"], correct, answer)
            p["results"].append(correct)
            p["idx"] += 1
            st.rerun()

    elif p["mode"] == "dictation":
        tts_url = client.get_tts_url(q["english"], "en")
        st.audio(tts_url, format="audio/mpeg")
        st.caption("🎧 听音频，拼写对应的英文单词")
        answer = st.text_input("输入英文", key=f"dict_{q['word_id']}_{p['idx']}")
        col_ok, col_skip = st.columns(2)
        with col_ok:
            if st.button("✅ 提交", use_container_width=True):
                correct = answer.strip().lower() == q["english"].lower()
                if correct:
                    st.success("✅ 正确！")
                else:
                    st.error(f"❌ 错误，正确答案: **{q['english']}**")
                _bg_submit(sid, q["word_id"], correct, answer)
                p["results"].append(correct)
                p["idx"] += 1
                st.rerun()
        with col_skip:
            if st.button("⏭ 跳过", use_container_width=True):
                _bg_submit(sid, q["word_id"], False, "")
                p["results"].append(False)
                p["idx"] += 1
                st.rerun()

# ── 练习结束（本地即时展示 + 后台调 finish）────────────
elif practice_done:
    if not p["finished"]:
        threading.Thread(
            target=client.finish_practice,
            args=(p["session_id"],),
            daemon=True,
        ).start()
        p["finished"] = True

    st.balloons()
    st.subheader("🎉 练习完成！")
    total = len(p["results"])
    correct = sum(p["results"])
    accuracy = round(correct / total * 100, 1) if total > 0 else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("总题数", total)
    col2.metric("正确数", correct)
    col3.metric("正确率", f"{accuracy}%")

    # ── 答题回顾 ─────────────────────────────────────────
    st.subheader("📝 答题回顾")
    sid = p["session_id"]
    member_id = st.session_state.get("member_id", 1)
    for i, q in enumerate(p["questions"]):
        is_correct = p["results"][i]
        if is_correct:
            st.markdown(f"✅ **{q['english']}** — {q['chinese']}")
        else:
            col_w, col_btn = st.columns([5, 1])
            with col_w:
                st.markdown(f"❌ **{q['english']}** — {q['chinese']}")
            with col_btn:
                if st.button("改标", key=f"fix_{i}"):
                    _bg_submit(sid, q["word_id"], True)
                    p["results"][i] = True
                    st.rerun()

    # ── 单元学习进度 ─────────────────────────────────────
    st.subheader("📊 单元进度")
    level_labels = {"unlearned": "🔴", "learning": "🟠", "familiar": "🔵", "permanent": "🟢"}
    # 缓存 units 列表用于显示标题
    if "_prac_units" not in st.session_state:
        resp = client.list_units(page_size=100)
        st.session_state["_prac_units"] = resp["data"]["items"] if resp["code"] == 200 else []
    unit_map = {u["id"]: u["title"] for u in st.session_state["_prac_units"]}

    for uid in p["unit_ids"]:
        stats = client.get_stats_unit(uid, member_id)
        if stats["code"] != 200:
            continue
        s = stats["data"]
        title = unit_map.get(uid, f"Unit {uid}")
        with st.container(border=True):
            st.markdown(f"**{title}**")
            rate = s["mastered_count"] / s["total_words"] if s["total_words"] > 0 else 0
            st.progress(rate, text=f"掌握率 {s['mastery_rate']}%")
            dist = s["mastery_distribution"]
            cols = st.columns(4)
            for j, (lv, emoji) in enumerate(level_labels.items()):
                label = {"unlearned": "未学习", "learning": "学习中", "familiar": "熟悉", "permanent": "永久"}[lv]
                cols[j].caption(f"{emoji} {label} {dist[lv]}")

    if st.button("🔄 再来一次"):
        st.session_state.prac = {
            "questions": [], "idx": 0, "session_id": None,
            "results": [], "mode": None, "unit_ids": [], "finished": False,
        }
        st.rerun()
