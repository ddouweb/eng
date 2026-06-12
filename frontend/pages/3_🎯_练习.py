import random
import threading
import time

import streamlit as st
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


def _bg_submit(session_id, word_id, is_correct, user_answer=None):
    threading.Thread(
        target=client.submit_answer,
        args=(session_id, word_id, is_correct),
        kwargs={"user_answer": user_answer},
        daemon=True,
    ).start()


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
    if "_prac_units" not in st.session_state:
        resp = client.list_units(page_size=100)
        st.session_state["_prac_units"] = resp["data"]["items"] if resp["code"] == 200 else []

    units = st.session_state["_prac_units"]
    if not units:
        st.info("还没有 Unit，请先添加单词。")
        st.stop()

    # Unit 选择 — 点击药丸切换
    unit_names = [u["title"] for u in units]
    unit_id_map = {u["title"]: u["id"] for u in units}
    selected_names = st.pills("📚 选择 Unit", unit_names, selection_mode="multi")
    selected_ids = [unit_id_map[n] for n in (selected_names or [])]

    # 题目数量 — 预设按钮
    count_opts = [5, 10, 15, 20, 30]
    count = st.pills("📝 题目数量", count_opts, default=10,
                     format_func=lambda x: f"{x} 题") or 10

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
        st.markdown(f"### {q['english']}")
        if st.button("显示答案" if not st.session_state.fc_show else "隐藏答案"):
            st.session_state.fc_show = not st.session_state.fc_show
        if st.session_state.fc_show:
            st.info(f"**{q['chinese']}**")
        col_ok, col_fail = st.columns(2)
        with col_ok:
            if st.button("✅ 认识", use_container_width=True):
                _bg_submit(sid, q["word_id"], True)
                p["results"].append(True); p["idx"] += 1
                st.session_state.fc_show = False; st.rerun()
        with col_fail:
            if st.button("❌ 不认识", use_container_width=True):
                _bg_submit(sid, q["word_id"], False, q["english"])
                p["results"].append(False); p["idx"] += 1
                st.session_state.fc_show = False; st.rerun()

    # ═══ 英→中 选择 ════════════════════════════════════
    elif p["mode"] == "choice":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        st.markdown(f"### {q['english']}")
        options = q.get("options", [q["chinese"]])
        answer = st.radio("选择正确的中文释义：", options, key=f"ch_{q['word_id']}")
        if st.button("确认", key=f"ch_sub_{q['word_id']}"):
            correct = answer == q["chinese"]
            if correct: st.success("✅ 正确！")
            else: st.error(f"❌ 正确答案: **{q['chinese']}**")
            _bg_submit(sid, q["word_id"], correct, answer)
            p["results"].append(correct); p["idx"] += 1; st.rerun()

    # ═══ 中→英 选择 ════════════════════════════════════
    elif p["mode"] == "cn2en_choice":
        q = p["questions"][p["idx"]]
        st.progress(p["idx"] / total, text=f"第 {p['idx'] + 1} / {total} 题")
        st.markdown(f"### {q['chinese']}")
        options = q.get("en_options", [q["english"]])
        answer = st.radio("选择正确的英文：", options, key=f"ce_{q['word_id']}")
        if st.button("确认", key=f"ce_sub_{q['word_id']}"):
            correct = answer == q["english"]
            if correct: st.success("✅ 正确！")
            else: st.error(f"❌ 正确答案: **{q['english']}**")
            _bg_submit(sid, q["word_id"], correct, answer)
            p["results"].append(correct); p["idx"] += 1; st.rerun()

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
    if not p["finished"]:
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

    st.subheader("📝 答题回顾")
    for i, q in enumerate(p["questions"]):
        is_correct = p["results"][i] if i < len(p["results"]) else False
        if is_correct:
            st.markdown(f"✅ **{q['english']}** — {q['chinese']}")
        else:
            col_w, col_btn = st.columns([5, 1])
            with col_w:
                st.markdown(f"❌ **{q['english']}** — {q['chinese']}")
            with col_btn:
                if st.button("改标", key=f"fix_{i}"):
                    _bg_submit(sid, q["word_id"], True)
                    p["results"][i] = True; st.rerun()

    st.subheader("📊 单元进度")
    level_emoji = {"unlearned": "🔴", "learning": "🟠", "familiar": "🔵", "permanent": "🟢"}
    level_name = {"unlearned": "未学习", "learning": "学习中", "familiar": "熟悉", "permanent": "永久"}
    if "_prac_units" not in st.session_state:
        resp = client.list_units(page_size=100)
        st.session_state["_prac_units"] = resp["data"]["items"] if resp["code"] == 200 else []
    unit_map = {u["id"]: u["title"] for u in st.session_state["_prac_units"]}
    for uid in p["unit_ids"]:
        stats = client.get_stats_unit(uid, member_id)
        if stats["code"] != 200:
            continue
        s = stats["data"]
        with st.container(border=True):
            st.markdown(f"**{unit_map.get(uid, f'Unit {uid}')}**")
            rate = s["mastered_count"] / s["total_words"] if s["total_words"] > 0 else 0
            st.progress(rate, text=f"掌握率 {s['mastery_rate']}%")
            dist = s["mastery_distribution"]
            cols = st.columns(4)
            for j, (lv, em) in enumerate(level_emoji.items()):
                cols[j].caption(f"{em} {level_name[lv]} {dist[lv]}")

    if st.button("🔄 再来一次"):
        for key in list(st.session_state.keys()):
            if any(key.startswith(pfx) for pfx in ("mg", "fm", "mf", "tc", "fc_", "scr_", "mf_opts_")):
                del st.session_state[key]
        st.session_state.prac = {
            "questions": [], "idx": 0, "session_id": None,
            "results": [], "mode": None, "unit_ids": [], "finished": False,
        }
        st.rerun()
