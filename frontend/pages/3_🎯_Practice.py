import streamlit as st
from api_client import client

st.header("🎯 练习")

# ── 选择练习配置 ─────────────────────────────────────
resp = client.list_units(page_size=100)
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，请先添加单词。")
    st.stop()

unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}
selected_keys = st.multiselect("选择 Unit", list(unit_options.keys()))
selected_ids = [unit_options[k] for k in selected_keys]

mode = st.selectbox("练习模式", ["flashcard", "spelling", "choice"],
                    format_func=lambda x: {"flashcard": "🃏 单词卡", "spelling": "✏️ 拼写", "choice": "🔘 选择题"}[x])
count = st.slider("题目数量", 5, 30, 10)

# ── 练习状态管理 ─────────────────────────────────────
if "practice_questions" not in st.session_state:
    st.session_state.practice_questions = []
    st.session_state.practice_idx = 0
    st.session_state.practice_session_id = None
    st.session_state.practice_results = []

if st.button("🚀 开始练习", disabled=not selected_ids):
    resp = client.start_practice(member_id=1, mode=mode, unit_ids=selected_ids, count=count)
    if resp["code"] == 200:
        st.session_state.practice_questions = resp["data"]["questions"]
        st.session_state.practice_session_id = resp["data"]["session_id"]
        st.session_state.practice_idx = 0
        st.session_state.practice_results = []
        st.rerun()
    else:
        st.error(resp["message"])

# ── 练习进行中 ───────────────────────────────────────
questions = st.session_state.practice_questions
session_id = st.session_state.practice_session_id
idx = st.session_state.practice_idx

if questions and idx < len(questions):
    q = questions[idx]
    total = len(questions)
    st.progress((idx) / total, text=f"第 {idx + 1} / {total} 题")

    if mode == "flashcard":
        if "fc_show" not in st.session_state:
            st.session_state.fc_show = False
        st.markdown(f"### {q['english']}")
        if st.button("显示答案" if not st.session_state.fc_show else "隐藏答案", key=f"fc_flip_{idx}"):
            st.session_state.fc_show = not st.session_state.fc_show
        if st.session_state.fc_show:
            st.info(f"**{q['chinese']}**")

        col_ok, col_fail = st.columns(2)
        with col_ok:
            if st.button("✅ 认识", key=f"fc_ok_{idx}", use_container_width=True):
                client.submit_answer(session_id, q["word_id"], True)
                st.session_state.practice_results.append(True)
                st.session_state.fc_show = False
                st.session_state.practice_idx += 1
                st.rerun()
        with col_fail:
            if st.button("❌ 不认识", key=f"fc_fail_{idx}", use_container_width=True):
                client.submit_answer(session_id, q["word_id"], False, q["english"])
                st.session_state.practice_results.append(False)
                st.session_state.fc_show = False
                st.session_state.practice_idx += 1
                st.rerun()

    elif mode == "spelling":
        from components.spelling_input import render as spelling
        answer = spelling(q["chinese"], q["word_id"])
        if answer is not None:
            correct = answer.lower() == q["english"].lower()
            if correct:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 错误，正确答案: **{q['english']}**")
            client.submit_answer(session_id, q["word_id"], correct, answer)
            st.session_state.practice_results.append(correct)
            st.session_state.practice_idx += 1
            st.rerun()

    elif mode == "choice":
        options = q.get("options", [q["chinese"]])
        from components.choice_quiz import render as choice
        answer = choice(q["english"], options, q["chinese"], q["word_id"])
        if answer is not None:
            correct = answer == q["chinese"]
            if correct:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 错误，正确答案: **{q['chinese']}**")
            client.submit_answer(session_id, q["word_id"], correct, answer)
            st.session_state.practice_results.append(correct)
            st.session_state.practice_idx += 1
            st.rerun()

# ── 练习结束 ─────────────────────────────────────────
elif questions and idx >= len(questions) and session_id:
    st.balloons()
    st.subheader("🎉 练习完成！")
    resp = client.finish_practice(session_id)
    if resp["code"] == 200:
        data = resp["data"]
        col1, col2, col3 = st.columns(3)
        col1.metric("总题数", data["total_count"])
        col2.metric("正确数", data["correct_count"])
        col3.metric("正确率", f"{data['accuracy']}%")

    if st.button("🔄 再来一次"):
        st.session_state.practice_questions = []
        st.session_state.practice_idx = 0
        st.session_state.practice_session_id = None
        st.session_state.practice_results = []
        st.rerun()
