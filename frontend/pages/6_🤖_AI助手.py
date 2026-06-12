import streamlit as st
from api_client import client
from components.ai_helpers import ai_kwargs, require_ai_key

st.header("🤖 AI 助手")

resp = client.list_units(page_size=100)
if resp["code"] != 200:
    st.error(resp["message"])
    st.stop()

units = resp["data"]["items"]
if not units:
    st.info("还没有 Unit，请先添加单词。")
    st.stop()

unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}

tab_dialogue, tab_exercise = st.tabs(["💬 场景对话", "📝 AI 练习"])

# ── 场景对话 ────────────────────────────────────────────
with tab_dialogue:
    st.subheader("💬 场景对话生成")
    st.caption("选择单元和场景，AI 会用这些单词生成一段英语对话。")

    sel_keys_d = st.multiselect("选择 Unit", list(unit_options.keys()), key="dlg_units")
    sel_ids_d = [unit_options[k] for k in sel_keys_d]

    scenario = st.selectbox("对话场景", [
        "日常对话", "购物", "学校", "家庭", "餐厅", "旅行", "看病", "天气",
    ], key="dlg_scenario")

    if st.button("生成对话", disabled=not sel_ids_d, key="dlg_gen"):
        if require_ai_key():
            with st.spinner("AI 正在生成对话..."):
                resp = client.generate_dialogue(sel_ids_d, scenario, **ai_kwargs())
            if resp["code"] == 200:
                st.session_state.dialogue_result = resp["data"]
            else:
                st.error(resp["message"])

    if "dialogue_result" in st.session_state:
        data = st.session_state.dialogue_result
        if data.get("scenario"):
            st.info(f"**场景：{data['scenario']}**")
        for line in data.get("lines", []):
            role = line["role"]
            icon = {"teacher": "👩‍🏫", "student": "👦", "narrator": "📖"}.get(role, "💬")
            with st.chat_message(role):
                st.markdown(f"{icon} **{role}**")
                st.markdown(f"**{line['english']}**")
                st.caption(line["chinese"])

# ── AI 练习 ────────────────────────────────────────────
with tab_exercise:
    st.subheader("📝 AI 练习题生成")
    st.caption("选择单元和题型，AI 会生成结构化练习题。")

    sel_keys_e = st.multiselect("选择 Unit", list(unit_options.keys()), key="ex_units")
    sel_ids_e = [unit_options[k] for k in sel_keys_e]

    ex_mode = st.selectbox("题型", ["choice", "fill"],
                           format_func=lambda x: {"choice": "🔘 选择题", "fill": "✏️ 填空题"}[x],
                           key="ex_mode")

    if st.button("生成练习", disabled=not sel_ids_e, key="ex_gen"):
        if require_ai_key():
            with st.spinner("AI 正在生成练习题..."):
                resp = client.generate_exercise(sel_ids_e, ex_mode, **ai_kwargs())
            if resp["code"] == 200:
                st.session_state.exercise_result = resp["data"]
                st.session_state.exercise_answers = {}
                st.session_state.exercise_submitted = False
            else:
                st.error(resp["message"])

    if "exercise_result" in st.session_state and not st.session_state.get("exercise_submitted"):
        items = st.session_state.exercise_result["items"]
        for i, item in enumerate(items):
            st.markdown(f"**Q{i + 1}. {item['question']}**")
            if item.get("options"):
                answer = st.radio(
                    "选择答案", item["options"],
                    key=f"ex_ans_{i}", index=None,
                )
                st.session_state.exercise_answers[i] = answer
            else:
                answer = st.text_input("你的答案", key=f"ex_fill_{i}")
                st.session_state.exercise_answers[i] = answer
            st.divider()

        if st.button("提交答案", key="ex_submit"):
            st.session_state.exercise_submitted = True
            st.rerun()

    if st.session_state.get("exercise_submitted"):
        items = st.session_state.exercise_result["items"]
        answers = st.session_state.exercise_answers
        correct_count = 0
        for i, item in enumerate(items):
            user_ans = answers.get(i, "")
            is_correct = user_ans == item["answer"] if user_ans else False
            if is_correct:
                correct_count += 1
                st.success(f"✅ Q{i + 1}: {item['question']}\n\n你的答案: **{user_ans}**")
            else:
                st.error(f"❌ Q{i + 1}: {item['question']}\n\n你的答案: {user_ans or '(未作答)'} ｜ 正确答案: **{item['answer']}**")
            if item.get("explanation"):
                st.caption(f"💡 {item['explanation']}")
            st.divider()

        total = len(items)
        st.metric("正确率", f"{correct_count}/{total} ({correct_count / total * 100:.0f}%)" if total else "0%")
        if st.button("重新生成"):
            del st.session_state.exercise_result
            del st.session_state.exercise_answers
            del st.session_state.exercise_submitted
            st.rerun()
