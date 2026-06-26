import random
import threading
import time
from datetime import date

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False

from api_client import client

MODES = {
    "flashcard": "🃏 单词卡",
    "choice": "🔘 英→中 选择",
    "cn2en_choice": "🔘 中→英 选择",
    "spelling": "✏️ 中→英 拼写",
    "en2cn_write": "📝 英→中 默写",
    "dictation": "🎧 听写",
    "matching": "🔗 连连看",
    "timed_challenge": "⏱️ 限时挑战",
    "scramble": "🔀 打乱重排",
    "memory_flash": "🧠 记忆闪卡",
    "flip_match": "🔍 翻牌寻配",
}

TAG_OPTIONS = ["favorite", "high_freq", "exam_focus", "excluded", "memorized"]
TAG_EMOJI = {
    "favorite": "⭐收藏",
    "high_freq": "🔥高频",
    "exam_focus": "📚考试",
    "excluded": "❌排除",
    "memorized": "✅已记",
}


def _bg_submit(session_id, word_id, is_correct, user_answer=None):
    threading.Thread(
        target=client.submit_answer,
        args=(session_id, word_id, is_correct),
        kwargs={"user_answer": user_answer},
        daemon=True,
    ).start()


def _restart_practice():
    """清空本轮所有 UI 状态，回到配置页。"""
    for key in list(st.session_state.keys()):
        if any(key.startswith(pfx) for pfx in ("mg", "fm", "mf", "tc", "fc_", "scr_", "mf_opts_", "tags_pills_")):
            del st.session_state[key]
    st.session_state.prac = {
        "questions": [], "idx": 0, "session_id": None,
        "results": [], "mode": None, "unit_ids": [], "finished": False,
    }
    # 重新拉一次今日计划快照，反映刚刚的练习进度
    st.session_state.pop("_today_plan_snapshot", None)
    st.rerun()


def _gen_en_options(q, all_questions, n=4):
    distractors = [x["english"] for x in all_questions if x["word_id"] != q["word_id"]]
    if len(distractors) < n - 1:
        distractors.extend(["???"] * (n - 1 - len(distractors)))
    picked = random.sample(distractors, min(n - 1, len(distractors)))
    opts = picked + [q["english"]]
    random.shuffle(opts)
    return opts


def _gen_cn_options(q, all_questions, n=4):
    distractors = [x["chinese"] for x in all_questions if x["word_id"] != q["word_id"]]
    if len(distractors) < n - 1:
        distractors.extend(["???"] * (n - 1 - len(distractors)))
    picked = random.sample(distractors, min(n - 1, len(distractors)))
    opts = picked + [q["chinese"]]
    random.shuffle(opts)
    return opts


def _scramble(word):
    letters = list(word)
    for _ in range(20):
        random.shuffle(letters)
        if "".join(letters) != word:
            return "".join(letters)
    return word[:-1] + word[0] + word[1:-1]


st.header("🎯 练习")

# ── 状态初始化 ─────────────────────────────────────────
if "prac" not in st.session_state:
    st.session_state.prac = {
        "questions": [], "idx": 0, "session_id": None,
        "results": [], "mode": None, "unit_ids": [], "finished": False,
    }

p = st.session_state.prac
in_practice = bool(p["questions"]) and p["idx"] < len(p["questions"])
practice_done = bool(p["questions"]) and p["idx"] >= len(p["questions"])

# ── 配置区 ─────────────────────────────────────────────
if not in_practice and not practice_done:
    if "_prac_units" not in st.session_state or (
        not st.session_state["_prac_units"] and client.get_token()
    ):
        resp = client.list_all_units()
        st.session_state["_prac_units"] = resp["data"]["items"] if resp["code"] == 200 else []

    units = st.session_state["_prac_units"]
    if not units:
        st.info("还没有 Unit，请先添加单词。")
        st.stop()

    # ── 今日计划快捷入口 ───────────────────────────────
    member_id = st.session_state.get("member_id", 1)
    if "_today_plan_snapshot" not in st.session_state and client.get_token():
        snapshot = []
        plans_resp = client.list_plans(status="active")
        if plans_resp["code"] == 200:
            today_str = str(date.today())
            for plan in plans_resp["data"]:
                det = client.get_plan(plan["id"])
                if det["code"] != 200:
                    continue
                tasks = det["data"].get("tasks", []) or []
                today_tasks = [t for t in tasks if t["task_date"] == today_str]
                # 按 task_type 分桶（首版每天最多一条 task）
                by_type = {}
                for t in today_tasks:
                    by_type.setdefault(t["task_type"], t)
                snapshot.append({
                    "plan_id": plan["id"],
                    "plan_name": plan["name"],
                    "unit_ids": det["data"].get("unit_ids", []),
                    "tasks": by_type,
                })
        st.session_state["_today_plan_snapshot"] = snapshot

    today_snapshot = st.session_state.get("_today_plan_snapshot", [])
    if today_snapshot:
        with st.container(border=True):
            st.markdown("### 📅 今日计划")
            st.caption(f"共 {len(today_snapshot)} 个进行中的计划 · 数据每小时不自动刷新，刷新页面可重读")

            # 聚合：学习日/周复习/月复习/错题刷 各自剩余题量
            learn_remain_new = 0
            learn_remain_review = 0
            weekly_remain = 0
            monthly_remain = 0
            drill_remain = 0
            agg_unit_ids: set[int] = set()
            has_learn = False
            has_weekly = False
            has_monthly = False
            has_drill = False
            learn_done = True
            weekly_done = True
            monthly_done = True
            drill_done = True

            for item in today_snapshot:
                agg_unit_ids.update(item["unit_ids"])
                t_by_type = item["tasks"]
                if "learn" in t_by_type:
                    has_learn = True
                    t = t_by_type["learn"]
                    if t["status"] != "completed":
                        learn_done = False
                    learn_remain_new += max(t["new_count"] - t["completed_new"], 0)
                    learn_remain_review += max(t["review_count"] - t["completed_review"], 0)
                if "weekly_review" in t_by_type:
                    has_weekly = True
                    t = t_by_type["weekly_review"]
                    if t["status"] != "completed":
                        weekly_done = False
                    weekly_remain += max(t["review_count"] - t["completed_review"], 0)
                if "monthly_review" in t_by_type:
                    has_monthly = True
                    t = t_by_type["monthly_review"]
                    if t["status"] != "completed":
                        monthly_done = False
                    monthly_remain += max(t["review_count"] - t["completed_review"], 0)
                if "wrong_word_drill" in t_by_type:
                    has_drill = True
                    t = t_by_type["wrong_word_drill"]
                    if t["status"] != "completed":
                        drill_done = False
                    drill_remain += max(t["review_count"] - t["completed_review"], 0)

            today_mode = st.selectbox(
                "练习模式",
                list(MODES.keys()),
                index=0,
                format_func=lambda m: MODES[m],
                key="today_mode_sel",
            )

            def _launch(task_type_label, count):
                """点击按钮启动对应 task_type 的练习。"""
                tt = None if task_type_label == "learn" else task_type_label
                resp = client.start_practice(
                    member_id=member_id,
                    mode=today_mode,
                    unit_ids=list(agg_unit_ids),
                    count=max(count, 5),
                    task_type=tt,
                )
                if resp["code"] == 200:
                    questions = resp["data"]["questions"]
                    if today_mode == "cn2en_choice":
                        for q in questions:
                            q["en_options"] = _gen_en_options(q, questions)
                    p.update({
                        "questions": questions,
                        "session_id": resp["data"]["session_id"],
                        "idx": 0, "results": [], "mode": today_mode,
                        "unit_ids": list(agg_unit_ids), "finished": False,
                        "fc_delay": 3.0, "fc_auto_next": False,
                    })
                    st.session_state.pop("_today_plan_snapshot", None)
                    st.rerun()
                else:
                    st.error(resp["message"])

            # ── 学习日 ──────────────────────────────────
            if has_learn:
                learn_total = learn_remain_new + learn_remain_review
                st.markdown(f"#### 📖 学习日（新词 {learn_remain_new} + 复习 {learn_remain_review}）")
                if learn_done:
                    st.success("🎉 今日学习已完成", icon="🎉")
                else:
                    if st.button(
                        f"🚀 开始今日学习（{learn_total} 题）",
                        use_container_width=True, type="primary",
                        disabled=(learn_total == 0 or not agg_unit_ids),
                        key="today_learn_btn",
                    ):
                        _launch("learn", learn_total)

            # ── 周复习日 ─────────────────────────────────
            if has_weekly:
                st.markdown(f"#### 🔁 周复习（本周练过的词）")
                if weekly_done:
                    st.success("🎉 周复习已完成", icon="🎉")
                else:
                    if st.button(
                        f"📖 本周复习（{weekly_remain} 题）",
                        use_container_width=True,
                        disabled=(weekly_remain == 0 or not agg_unit_ids),
                        key="today_weekly_btn",
                    ):
                        _launch("weekly_review", weekly_remain)

            # ── 月复习日 ─────────────────────────────────
            if has_monthly:
                st.markdown(f"#### 📚 月复习（本月练过的词）")
                if monthly_done:
                    st.success("🎉 月复习已完成", icon="🎉")
                else:
                    if st.button(
                        f"📚 本月复习（{monthly_remain} 题）",
                        use_container_width=True,
                        disabled=(monthly_remain == 0 or not agg_unit_ids),
                        key="today_monthly_btn",
                    ):
                        _launch("monthly_review", monthly_remain)

            # ── 错题刷（三轮） ──────────────────────────
            if has_drill:
                st.markdown(f"#### 🎯 错题冲刺（错过的词）")
                if drill_done:
                    st.success("🎉 今日错题已刷完", icon="🎉")
                else:
                    if st.button(
                        f"🎯 错题冲刺（{drill_remain} 题）",
                        use_container_width=True,
                        disabled=(drill_remain == 0 or not agg_unit_ids),
                        key="today_drill_btn",
                    ):
                        _launch("wrong_word_drill", drill_remain)

            # ── 什么 task 都没有 ──────────────────────
            if not (has_learn or has_weekly or has_monthly or has_drill):
                st.info("今日暂无任何任务")

        st.divider()

    # Unit 选择 — 点击药丸切换
    unit_names = [u["title"] for u in units]
    unit_id_map = {u["title"]: u["id"] for u in units}
    selected_names = st.pills("📚 选择 Unit", unit_names, selection_mode="multi")
    selected_ids = [unit_id_map[n] for n in (selected_names or [])]

    # 题目数量 — 预设按钮（"全部" 表示所有可练习单词）
    count_opts = [10, 20, 30, 50, 80, 100, 150, 200, "全部"]
    count_choice = st.pills("📝 题目数量", count_opts, default=50,
                            format_func=lambda x: "全部" if x == "全部" else f"{x} 题") or 50
    count = 2000 if count_choice == "全部" else count_choice

    # 单词卡自动/手动模式
    fc_auto_next = st.checkbox(
        "🃏 单词卡：答后自动下一题",
        value=False,
        disabled=not _HAS_AUTOREFRESH,
        help=(
            "勾选：点「认识/不认识」即终态，自动展示释义并在延时后切换下一题（依赖 streamlit-autorefresh）。"
            "不勾选：答后可反复修正标记，点「下一题」才提交最终答案"
        ) + ("" if _HAS_AUTOREFRESH else "（未安装 streamlit-autorefresh，仅支持手动模式）"),
    )
    fc_delay = 3.0
    if fc_auto_next:
        fc_delay = st.number_input(
            "自动下一题延时（秒）",
            min_value=0.5, max_value=10.0, value=3.0, step=0.5,
        )

    st.divider()
    st.markdown("**👇 选择模式，点击即开始**")

    # 模式卡片网格 — 点击直接开始练习
    mode_keys = list(MODES.keys())
    for row_start in range(0, len(mode_keys), 4):
        cols = st.columns(4)
        for i, key in enumerate(mode_keys[row_start:row_start + 4]):
            with cols[i]:
                if st.button(MODES[key], key=f"mode_{key}",
                             use_container_width=True, disabled=not selected_ids):
                    member_id = st.session_state.get("member_id", 1)
                    resp = client.start_practice(
                        member_id=member_id, mode=key,
                        unit_ids=selected_ids, count=count)
                    if resp["code"] == 200:
                        questions = resp["data"]["questions"]
                        if key == "cn2en_choice":
                            for q in questions:
                                q["en_options"] = _gen_en_options(q, questions)
                        p.update({
                            "questions": questions,
                            "session_id": resp["data"]["session_id"],
                            "idx": 0, "results": [], "mode": key,
                            "unit_ids": selected_ids, "finished": False,
                            "fc_delay": fc_delay,
                            "fc_auto_next": fc_auto_next,
                        })
                        st.rerun()
                    else:
                        st.error(resp["message"])

# ── 练习进行中 ─────────────────────────────────────────
if in_practice:
    sid = p["session_id"]
    total = len(p["questions"])

    # ── 中途退出 ───────────────────────────────────────
    col_quit_l, col_quit_r = st.columns([6, 1])
    with col_quit_l:
        st.caption(f"模式: {MODES.get(p['mode'], '')}")
    with col_quit_r:
        if st.button("⏹️ 结束"):
            p["idx"] = total
            st.rerun()

    # ═══ 单词卡 ════════════════════════════════════════
    if p["mode"] == "flashcard":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        if "fc_show" not in st.session_state:
            st.session_state.fc_show = False

        delay = p.get("fc_delay", 3.0)
        # 仅当用户勾选自动模式且 streamlit-autorefresh 已装才走自动路径
        auto_next = bool(p.get("fc_auto_next", True)) and _HAS_AUTOREFRESH
        answered = st.session_state.get("fc_answered", False)
        answer_time = st.session_state.get("fc_answer_time")
        pending = st.session_state.get("fc_pending_answer")  # True/False/None

        st.markdown(f"### {q['english']}")

        if not answered:
            # ── 阶段 1：未答 ───────────────────────────────
            if st.button(
                "显示答案" if not st.session_state.fc_show else "隐藏答案",
                key=f"fc_toggle_{p['idx']}",
            ):
                st.session_state.fc_show = not st.session_state.fc_show
                st.rerun()
            if st.session_state.fc_show:
                st.info(f"**{q['chinese']}**")
            col_ok, col_fail = st.columns(2)
            with col_ok:
                if st.button("✅ 认识", use_container_width=True, key=f"fc_ok_{p['idx']}"):
                    if auto_next:
                        _bg_submit(sid, q["word_id"], True)
                        p["results"].append(True)
                        st.session_state.fc_answer_time = time.time()
                    else:
                        st.session_state.fc_pending_answer = True
                    st.session_state.fc_answered = True
                    st.session_state.fc_show = True
                    st.rerun()
            with col_fail:
                if st.button("❌ 不认识", use_container_width=True, key=f"fc_fail_{p['idx']}"):
                    if auto_next:
                        _bg_submit(sid, q["word_id"], False, q["english"])
                        p["results"].append(False)
                        st.session_state.fc_answer_time = time.time()
                    else:
                        st.session_state.fc_pending_answer = False
                    st.session_state.fc_answered = True
                    st.session_state.fc_show = True
                    st.rerun()
        elif auto_next:
            # ── 阶段 2A：已答 · 自动模式 — 倒计时下一题 ──
            # 用 streamlit-autorefresh 在剩余时间后触发一次 rerun。
            # 与 button 触发的 rerun 一样，都是 streamlit 标准 rerun，
            # session_state 完全保留，不会出现 fragment 干扰 button 状态的问题。
            elapsed = time.time() - answer_time
            st.info(f"**{q['chinese']}**")
            if elapsed >= delay:
                p["idx"] += 1
                st.session_state.fc_answered = False
                st.session_state.fc_answer_time = None
                st.session_state.fc_pending_answer = None
                st.session_state.fc_show = False
                st.rerun()
            else:
                remaining = delay - elapsed
                # 调度一次自动 rerun：interval 比剩余多 100ms 防止过早触发
                st_autorefresh(
                    interval=int(remaining * 1000) + 100,
                    key=f"fc_ar_{p['idx']}_{int(answer_time * 1000)}",
                )
                col_info, col_next = st.columns([3, 2])
                with col_info:
                    st.caption(f"⏱️ {remaining:.1f}s 后自动下一题")
                with col_next:
                    if st.button("➡️ 下一题", use_container_width=True, key=f"fc_next_{p['idx']}"):
                        p["idx"] += 1
                        st.session_state.fc_answered = False
                        st.session_state.fc_answer_time = None
                        st.session_state.fc_pending_answer = None
                        st.session_state.fc_show = False
                        st.rerun()
        else:
            # ── 阶段 2B：已答 · 手动模式 — 可重标 + 下一题 ─
            st.info(f"**{q['chinese']}**")
            col_ok, col_fail = st.columns(2)
            with col_ok:
                label_ok = "✅ 已标记：认识" if pending is True else "✅ 认识"
                if st.button(
                    label_ok,
                    use_container_width=True,
                    key=f"fc_ok_{p['idx']}",
                    type="primary" if pending is True else "secondary",
                ):
                    st.session_state.fc_pending_answer = True
                    st.rerun()
            with col_fail:
                label_fail = "❌ 已标记：不认识" if pending is False else "❌ 不认识"
                if st.button(
                    label_fail,
                    use_container_width=True,
                    key=f"fc_fail_{p['idx']}",
                    type="primary" if pending is False else "secondary",
                ):
                    st.session_state.fc_pending_answer = False
                    st.rerun()
            if st.button(
                "➡️ 下一题",
                use_container_width=True,
                key=f"fc_next_{p['idx']}",
                disabled=(pending is None),
            ):
                # 提交最终答案（仅在下一题时提交一次）
                is_correct = pending is True
                _bg_submit(
                    sid, q["word_id"], is_correct,
                    None if is_correct else q["english"],
                )
                p["results"].append(is_correct)
                p["idx"] += 1
                st.session_state.fc_answered = False
                st.session_state.fc_pending_answer = None
                st.session_state.fc_show = False
                st.rerun()

    # ═══ 英→中 选择 ════════════════════════════════════
    elif p["mode"] == "choice":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        st.markdown(f"### {q['english']}")
        options = q.get("options", [q["chinese"]])
        answers = p.setdefault("answers", {})
        cur = answers.get(p["idx"])
        answered = cur is not None
        answer = st.radio(
            "选择正确的中文释义：", options,
            key=f"ch_{q['word_id']}",
            disabled=answered,
        )
        if not answered:
            if st.button("确认", key=f"ch_sub_{q['word_id']}", type="primary"):
                correct = answer == q["chinese"]
                if correct:
                    st.success("✅ 正确！")
                else:
                    st.error(f"❌ 正确答案: **{q['chinese']}**")
                _bg_submit(sid, q["word_id"], correct, answer)
                p["results"].append(correct)
                answers[p["idx"]] = {"answer": answer, "correct": correct}
                st.rerun()
        else:
            if cur["correct"]:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 你的答案: {cur['answer']}　|　正确答案: **{q['chinese']}**")
            col_prev, col_next = st.columns([1, 1])
            with col_prev:
                if st.button("⬅️ 上一题", use_container_width=True,
                             disabled=(p["idx"] == 0),
                             key=f"ch_prev_{q['word_id']}"):
                    p["idx"] -= 1
                    st.rerun()
            with col_next:
                btn_label = "➡️ 下一题" if p["idx"] < total - 1 else "✅ 完成练习"
                if st.button(btn_label, use_container_width=True, type="primary",
                             key=f"ch_next_{q['word_id']}"):
                    p["idx"] += 1
                    st.rerun()

    # ═══ 中→英 选择 ════════════════════════════════════
    elif p["mode"] == "cn2en_choice":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        st.markdown(f"### {q['chinese']}")
        options = q.get("en_options", [q["english"]])
        answers = p.setdefault("answers", {})
        cur = answers.get(p["idx"])
        answered = cur is not None
        answer = st.radio(
            "选择正确的英文：", options,
            key=f"ce_{q['word_id']}",
            disabled=answered,
        )
        if not answered:
            if st.button("确认", key=f"ce_sub_{q['word_id']}", type="primary"):
                correct = answer == q["english"]
                if correct:
                    st.success("✅ 正确！")
                else:
                    st.error(f"❌ 正确答案: **{q['english']}**")
                _bg_submit(sid, q["word_id"], correct, answer)
                p["results"].append(correct)
                answers[p["idx"]] = {"answer": answer, "correct": correct}
                st.rerun()
        else:
            if cur["correct"]:
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 你的答案: {cur['answer']}　|　正确答案: **{q['english']}**")
            col_prev, col_next = st.columns([1, 1])
            with col_prev:
                if st.button("⬅️ 上一题", use_container_width=True,
                             disabled=(p["idx"] == 0),
                             key=f"ce_prev_{q['word_id']}"):
                    p["idx"] -= 1
                    st.rerun()
            with col_next:
                btn_label = "➡️ 下一题" if p["idx"] < total - 1 else "✅ 完成练习"
                if st.button(btn_label, use_container_width=True, type="primary",
                             key=f"ce_next_{q['word_id']}"):
                    p["idx"] += 1
                    st.rerun()

    # ═══ 中→英 拼写 ════════════════════════════════════
    elif p["mode"] == "spelling":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        st.markdown(f"**中文：** {q['chinese']}")
        answer = st.text_input("输入英文拼写：", key=f"sp_{q['word_id']}")
        if st.button("提交", key=f"sp_sub_{q['word_id']}"):
            ans = answer.strip() if answer else ""
            correct = ans.lower() == q["english"].lower()
            if correct: st.success("✅ 正确！")
            else: st.error(f"❌ 正确答案: **{q['english']}**")
            _bg_submit(sid, q["word_id"], correct, ans)
            p["results"].append(correct); p["idx"] += 1; st.rerun()

    # ═══ 英→中 默写 ════════════════════════════════════
    elif p["mode"] == "en2cn_write":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        st.markdown(f"### {q['english']}")
        answer = st.text_input("输入中文释义：", key=f"ew_{q['word_id']}")
        if st.button("提交", key=f"ew_sub_{q['word_id']}"):
            ans = answer.strip() if answer else ""
            correct = ans == q["chinese"]
            if correct: st.success("✅ 正确！")
            else: st.error(f"❌ 正确答案: **{q['chinese']}**")
            _bg_submit(sid, q["word_id"], correct, ans)
            p["results"].append(correct); p["idx"] += 1; st.rerun()

    # ═══ 听写 ══════════════════════════════════════════
    elif p["mode"] == "dictation":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        tts_url = client.get_tts_url(q["english"], "en")
        st.audio(tts_url, format="audio/mpeg")
        st.caption("🎧 听音频，拼写对应的英文单词")
        answer = st.text_input("输入英文", key=f"dt_{q['word_id']}_{p['idx']}")
        col_ok, col_skip = st.columns(2)
        with col_ok:
            if st.button("✅ 提交", use_container_width=True):
                correct = answer.strip().lower() == q["english"].lower()
                if correct: st.success("✅ 正确！")
                else: st.error(f"❌ 正确答案: **{q['english']}**")
                _bg_submit(sid, q["word_id"], correct, answer)
                p["results"].append(correct); p["idx"] += 1; st.rerun()
        with col_skip:
            if st.button("⏭ 跳过", use_container_width=True):
                _bg_submit(sid, q["word_id"], False, "")
                p["results"].append(False); p["idx"] += 1; st.rerun()

    # ═══ 连连看 ════════════════════════════════════════
    elif p["mode"] == "matching":
        BATCH = 4
        if "mg" not in st.session_state:
            st.session_state.mg = {"batch": 0, "matched": set(), "sel_en": None}
        mg = st.session_state.mg
        start_i = mg["batch"] * BATCH
        end_i = min(start_i + BATCH, total)
        batch = p["questions"][start_i:end_i]
        if batch and len(mg["matched"]) >= len(batch):
            mg["batch"] += 1; mg["matched"] = set(); mg["sel_en"] = None
            p["idx"] = min(mg["batch"] * BATCH, total); st.rerun()
        if not batch:
            p["idx"] = total; st.rerun()
        overall = min(p["idx"] + len(mg["matched"]), total)
        st.progress(overall / total, text=f"第 {mg['batch'] + 1} 轮 · 已配对 {overall}/{total}")
        cn_key = f"mg_cn_{mg['batch']}"
        if cn_key not in st.session_state:
            st.session_state[cn_key] = random.sample(range(len(batch)), len(batch))
        st.caption("👉 先点左边英文，再点右边中文完成配对")
        col_en, col_cn = st.columns(2)
        with col_en:
            st.markdown("**English**")
            for q in batch:
                wid = q["word_id"]
                if wid in mg["matched"]:
                    st.button(f"✅ {q['english']}", disabled=True, key=f"me_{wid}")
                elif mg["sel_en"] == wid:
                    st.button(f"👉 {q['english']}", disabled=True, key=f"me_{wid}")
                else:
                    if st.button(q["english"], key=f"me_{wid}"):
                        mg["sel_en"] = wid; st.rerun()
        with col_cn:
            st.markdown("**中文**")
            for i in st.session_state[cn_key]:
                q = batch[i]; wid = q["word_id"]
                if wid in mg["matched"]:
                    st.button(f"✅ {q['chinese']}", disabled=True, key=f"mc_{wid}")
                else:
                    if st.button(q["chinese"], key=f"mc_{wid}"):
                        if mg["sel_en"] is not None:
                            if mg["sel_en"] == wid:
                                mg["matched"].add(wid)
                                _bg_submit(sid, wid, True); p["results"].append(True)
                            else:
                                _bg_submit(sid, mg["sel_en"], False, q["english"])
                                mg["wrong"] = mg.get("wrong", 0) + 1; p["results"].append(False)
                            mg["sel_en"] = None; st.rerun()

    # ═══ 限时挑战 ══════════════════════════════════════
    elif p["mode"] == "timed_challenge":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        TIME_LIMIT = 8
        if "tc_start" not in st.session_state:
            st.session_state.tc_start = time.time()
        elapsed = time.time() - st.session_state.tc_start
        remaining = max(0, TIME_LIMIT - elapsed)
        st.progress(remaining / TIME_LIMIT, text=f"⏱️ {remaining:.1f}s")
        if remaining > 0.5:
            st.markdown(f'<meta http-equiv="refresh" content="{max(1, int(remaining) + 1)}">',
                        unsafe_allow_html=True)
        if remaining <= 0:
            st.warning("⏰ 时间到！")
            _bg_submit(sid, q["word_id"], False, "")
            p["results"].append(False); p["idx"] += 1
            for k in ("tc_start", "tc_opts"): st.session_state.pop(k, None)
            st.rerun()
        st.markdown(f"### {q['english']}")
        if "tc_opts" not in st.session_state:
            st.session_state.tc_opts = _gen_cn_options(q, p["questions"])
        for i, opt in enumerate(st.session_state.tc_opts):
            if st.button(opt, key=f"tc_{q['word_id']}_{i}", use_container_width=True):
                correct = opt == q["chinese"]
                rt = time.time() - st.session_state.tc_start
                if correct: st.success(f"✅ 正确！反应 {rt:.1f}s")
                else: st.error(f"❌ 正确答案: **{q['chinese']}**")
                _bg_submit(sid, q["word_id"], correct, opt)
                p["results"].append(correct); p["idx"] += 1
                for k in ("tc_start", "tc_opts"): st.session_state.pop(k, None)
                st.rerun()

    # ═══ 打乱重排 ══════════════════════════════════════
    elif p["mode"] == "scramble":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        skey = f"scr_{q['word_id']}"
        if skey not in st.session_state:
            st.session_state[skey] = _scramble(q["english"])
        st.markdown(f"**中文释义：** {q['chinese']}")
        st.markdown(f"### {'  '.join(list(st.session_state[skey]))}")
        st.caption("将上面的字母重新排列成正确的英文单词")
        answer = st.text_input("输入答案：", key=f"scr_in_{q['word_id']}")
        if st.button("提交", key=f"scr_sub_{q['word_id']}"):
            ans = answer.strip() if answer else ""
            correct = ans.lower() == q["english"].lower()
            if correct: st.success("✅ 正确！")
            else: st.error(f"❌ 正确答案: **{q['english']}**")
            _bg_submit(sid, q["word_id"], correct, ans)
            p["results"].append(correct); p["idx"] += 1; st.rerun()

    # ═══ 记忆闪卡 ══════════════════════════════════════
    elif p["mode"] == "memory_flash":
        BATCH = 4
        if "mf" not in st.session_state:
            st.session_state.mf = {"batch": 0, "phase": "study", "idx": 0}
        mf = st.session_state.mf
        start_i = mf["batch"] * BATCH
        end_i = min(start_i + BATCH, total)
        batch = p["questions"][start_i:end_i]
        if not batch:
            p["idx"] = total; st.rerun()

        if mf["phase"] == "study":
            q = batch[mf["idx"]]
            st.info(f"📚 记住这些单词！({mf['idx'] + 1}/{len(batch)})")
            col1, col2 = st.columns(2)
            col1.markdown(f"### {q['english']}")
            col2.markdown(f"### {q['chinese']}")
            if st.button("下一张 ➡️", use_container_width=True):
                mf["idx"] += 1
                if mf["idx"] >= len(batch):
                    mf["phase"] = "quiz"; mf["idx"] = 0
                st.rerun()

        elif mf["phase"] == "quiz":
            q = batch[mf["idx"]]
            st.warning(f"🧠 回忆测试 ({mf['idx'] + 1}/{len(batch)})")
            st.markdown(f"### {q['english']}")
            okey = f"mf_opts_{q['word_id']}"
            if okey not in st.session_state:
                st.session_state[okey] = _gen_cn_options(q, p["questions"])
            answer = st.radio("选择正确的中文：", st.session_state[okey], key=f"mf_{q['word_id']}")
            if st.button("确认", key=f"mf_sub_{q['word_id']}"):
                correct = answer == q["chinese"]
                if correct: st.success("✅ 记忆力不错！")
                else: st.error(f"❌ 忘了吗？正确答案: **{q['chinese']}**")
                _bg_submit(sid, q["word_id"], correct, answer)
                p["results"].append(correct)
                mf["idx"] += 1
                if mf["idx"] >= len(batch):
                    mf["batch"] += 1; mf["phase"] = "study"; mf["idx"] = 0
                    p["idx"] = min(mf["batch"] * BATCH, total)
                st.rerun()

    # ═══ 翻牌寻配 ══════════════════════════════════════
    elif p["mode"] == "flip_match":
        BATCH = 4
        if "fm" not in st.session_state:
            cards = []
            for q in p["questions"][:BATCH]:
                cards.append({"wid": q["word_id"], "text": q["english"], "en": True})
                cards.append({"wid": q["word_id"], "text": q["chinese"], "en": False})
            random.shuffle(cards)
            st.session_state.fm = {
                "cards": cards, "flipped": [], "matched": set(),
                "attempts": 0, "batch": 0, "mismatch": False, "mm_cards": [],
            }
        fm = st.session_state.fm

        show_mm = fm["mismatch"]
        mm_set = set(fm["mm_cards"])
        if show_mm:
            st.error("❌ 不匹配！再试试")
            fm["mismatch"] = False; fm["mm_cards"] = []; fm["flipped"] = []

        if len(fm["matched"]) >= len(fm["cards"]):
            fm["batch"] += 1
            si = fm["batch"] * BATCH
            ei = min(si + BATCH, total)
            if si >= total:
                p["idx"] = total; st.rerun()
            batch_q = p["questions"][si:ei]
            cards = []
            for q in batch_q:
                cards.append({"wid": q["word_id"], "text": q["english"], "en": True})
                cards.append({"wid": q["word_id"], "text": q["chinese"], "en": False})
            random.shuffle(cards)
            fm.update({"cards": cards, "flipped": [], "matched": set(), "attempts": 0})
            p["idx"] = min(fm["batch"] * BATCH, total); st.rerun()

        n_pairs = len(fm["matched"]) // 2 + (fm["batch"] * BATCH)
        st.progress(n_pairs / total, text=f"第 {fm['batch'] + 1} 轮 · 翻牌 {fm['attempts']} 次")
        st.caption("🔍 翻两张牌，找到英文和中文的配对")

        cols_per_row = 4
        for row_start in range(0, len(fm["cards"]), cols_per_row):
            cols = st.columns(cols_per_row)
            for ci in range(cols_per_row):
                idx = row_start + ci
                if idx >= len(fm["cards"]):
                    break
                card = fm["cards"][idx]
                with cols[ci]:
                    face_up = idx in fm["matched"] or idx in fm["flipped"] or (show_mm and idx in mm_set)
                    if face_up:
                        flag = "🇬🇧" if card["en"] else "🇨🇳"
                        st.button(f"{flag} {card['text']}", disabled=True, key=f"fm_{idx}",
                                  use_container_width=True)
                    else:
                        if st.button("🂠", key=f"fm_{idx}", use_container_width=True):
                            if len(fm["flipped"]) < 2:
                                fm["flipped"].append(idx)
                                if len(fm["flipped"]) == 2:
                                    fm["attempts"] += 1
                                    c1, c2 = fm["cards"][fm["flipped"][0]], fm["cards"][fm["flipped"][1]]
                                    if c1["wid"] == c2["wid"] and c1["en"] != c2["en"]:
                                        fm["matched"].update(fm["flipped"])
                                        _bg_submit(sid, c1["wid"], True)
                                        p["results"].append(True)
                                        fm["flipped"] = []
                                    else:
                                        _bg_submit(sid, c1["wid"], False, c2["text"])
                                        p["results"].append(False)
                                        fm["mismatch"] = True
                                        fm["mm_cards"] = list(fm["flipped"])
                                        fm["flipped"] = []
                                st.rerun()

# ── 练习结束 ───────────────────────────────────────────
elif practice_done:
    first_finish = not p["finished"]
    if first_finish:
        threading.Thread(target=client.finish_practice, args=(p["session_id"],), daemon=True).start()
        p["finished"] = True
        st.balloons()

    st.subheader("🎉 练习完成！")
    sid = p["session_id"]
    member_id = st.session_state.get("member_id", 1)
    total = len(p["results"])
    correct = sum(p["results"])
    accuracy = round(correct / total * 100, 1) if total > 0 else 0
    col1, col2, col3 = st.columns(3)
    col1.metric("总题数", total)
    col2.metric("正确数", correct)
    col3.metric("正确率", f"{accuracy}%")

    if st.button("🔄 再来一次", use_container_width=True, type="primary"):
        _restart_practice()

    st.subheader("📝 答题回顾 · 可标记单词")
    st.caption("点击标签药丸即可切换：⭐收藏 🔥高频 📚考试 ❌排除 ✅已记")
    for i, q in enumerate(p["questions"]):
        is_correct = p["results"][i] if i < len(p["results"]) else False
        with st.container(border=True):
            col_w, col_btn = st.columns([5, 1])
            with col_w:
                icon = "✅" if is_correct else "❌"
                st.markdown(f"{icon} **{q['english']}** — {q['chinese']}")
            with col_btn:
                if not is_correct and st.button("改标", key=f"fix_{i}"):
                    _bg_submit(sid, q["word_id"], True)
                    p["results"][i] = True
                    st.rerun()

            current_tags = list(q.get("tags", []))
            selected = st.pills(
                "标签",
                TAG_OPTIONS,
                selection_mode="multi",
                default=[t for t in current_tags if t in TAG_OPTIONS],
                format_func=lambda t: TAG_EMOJI.get(t, t),
                key=f"tags_pills_{q['word_id']}_{i}",
            )
            new_tags = list(selected or [])
            if new_tags != current_tags:
                client.set_tags(q["word_id"], new_tags)
                q["tags"] = new_tags
                st.toast(f"已更新 {q['english']} 的标签")
                st.rerun()

    st.subheader("📊 单元进度")
    level_emoji = {"unlearned": "🔴", "learning": "🟠", "familiar": "🔵", "permanent": "🟢"}
    if "_prac_units" not in st.session_state or (
        not st.session_state["_prac_units"] and client.get_token()
    ):
        resp = client.list_all_units()
        st.session_state["_prac_units"] = resp["data"]["items"] if resp["code"] == 200 else []
    unit_map = {u["id"]: u["title"] for u in st.session_state["_prac_units"]}

    UNIT_COLS = 3
    unit_ids = p["unit_ids"]
    for row_start in range(0, len(unit_ids), UNIT_COLS):
        cols = st.columns(UNIT_COLS)
        for i, uid in enumerate(unit_ids[row_start:row_start + UNIT_COLS]):
            with cols[i]:
                stats = client.get_stats_unit(uid, member_id)
                if stats["code"] != 200:
                    st.caption(f"{unit_map.get(uid, f'Unit {uid}')} · 加载失败")
                    continue
                s = stats["data"]
                rate = s["mastered_count"] / s["total_words"] if s["total_words"] > 0 else 0
                dist = s["mastery_distribution"]
                dist_str = "  ".join(f"{level_emoji[lv]} {dist[lv]}" for lv in level_emoji)
                st.caption(f"**{unit_map.get(uid, f'Unit {uid}')}** · 掌握率 {s['mastery_rate']}%")
                st.progress(rate, text=dist_str)

    if st.button("🔄 再来一次"):
        _restart_practice()
