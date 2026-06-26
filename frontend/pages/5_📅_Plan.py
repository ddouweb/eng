import streamlit as st
from datetime import date
from api_client import client

st.header("📅 学习计划")

# ── 创建计划 ────────────────────────────────────────────
with st.expander("➕ 创建新计划", expanded=False):
    resp = client.list_all_units()
    if resp["code"] != 200:
        st.error(resp["message"])
        st.stop()

    units = resp["data"]["items"]
    if not units:
        st.info("还没有 Unit，请先添加单词。")
        st.stop()

    unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}

    name = st.text_input("计划名称", placeholder="例：在职考研英语一轮", key="plan_name")
    selected_keys = st.multiselect("选择 Unit", list(unit_options.keys()), key="plan_units")
    selected_ids = [unit_options[k] for k in selected_keys]
    daily_goal = st.number_input("每日目标（新词数）", min_value=1, max_value=200, value=15, key="plan_goal")
    deadline = st.date_input("截止日期（可选）", value=None, key="plan_deadline")

    # 学习日（默认周一到周五）
    weekday_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    selected_wd_labels = st.multiselect(
        "学习日（其余为周复习日）",
        weekday_labels,
        default=weekday_labels[:5],
        key="plan_weekdays",
    )
    learn_weekdays = [weekday_labels.index(x) for x in selected_wd_labels]

    # 月复习日
    mrd_options = ["无", "月末（最后一天）"] + [str(i) for i in range(1, 29)]
    mrd_choice = st.selectbox("月复习日", mrd_options, index=0, key="plan_mrd",
                              help="月复习日赶上工作日时，当天只做月复习，不学新词")
    if mrd_choice == "无":
        monthly_review_day = None
    elif "月末" in mrd_choice:
        monthly_review_day = 31
    else:
        monthly_review_day = int(mrd_choice)

    # 计划类型（首轮/二轮/三轮）
    plan_type_options = {
        "首轮（学新词 + 滚动复习）": "forward",
        "二轮（纯复习，不学新词）": "review_only",
        "三轮（错题冲刺）": "wrong_word_drill",
    }
    pt_label = st.selectbox(
        "计划类型", list(plan_type_options.keys()), index=0, key="plan_type",
        help="首轮 = 学新词；二轮 = 不学新词，每天复习；三轮 = 只刷错题"
    )
    plan_type = plan_type_options[pt_label]

    # 起始日（默认今天，二轮/三轮可设未来日期）
    start_date = st.date_input(
        "起始日（二/三轮可设未来日期）", value=None, key="plan_start",
        help="默认今天。设到未来时，计划存在但到期前不产出每日任务"
    )

    if st.button("创建计划", disabled=not name or not selected_ids or not learn_weekdays):
        deadline_str = str(deadline) if deadline else None
        start_date_str = str(start_date) if start_date else None
        resp = client.create_plan(
            name=name, daily_goal=daily_goal,
            unit_ids=selected_ids, deadline=deadline_str,
            learn_weekdays=learn_weekdays,
            monthly_review_day=monthly_review_day,
            start_date=start_date_str,
            plan_type=plan_type,
        )
        if resp["code"] == 200:
            st.success(f"计划「{name}」创建成功！")
            st.rerun()
        else:
            st.error(resp["message"])

# ── 计划列表 ────────────────────────────────────────────
tab_all, tab_active, tab_paused = st.tabs(["全部", "进行中", "已暂停"])

for tab, status_filter in [(tab_all, None), (tab_active, "active"), (tab_paused, "paused")]:
    # st.tabs 内部三个 tab 的 widget 都会渲染，key 必须加 tab 前缀避免冲突
    kp = status_filter or "all"
    with tab:
        resp = client.list_plans(status=status_filter)
        if resp["code"] != 200:
            st.error(resp["message"])
            continue

        plans = resp["data"]
        if not plans:
            st.info("暂无计划" + (f"（{status_filter}）" if status_filter else ""))
            continue

        for p in plans:
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    status_icon = {"active": "🟢", "paused": "⏸️", "completed": "✅"}.get(p["status"], "⚪")
                    pt_label = {"forward": "首轮", "review_only": "二轮", "wrong_word_drill": "三轮"}.get(p.get("plan_type", "forward"), "")
                    pt_emoji = {"forward": "🌱", "review_only": "🔁", "wrong_word_drill": "🎯"}.get(p.get("plan_type", "forward"), "")
                    st.markdown(f"### {status_icon} {p['name']}")
                    st.caption(
                        f"{pt_emoji} {pt_label} ｜ 每日目标: {p['daily_goal']} 词"
                        f" ｜ 起始: {p.get('start_date') or '-'} ｜ 截止: {p.get('deadline') or '未设置'}"
                    )
                with col2:
                    st.caption(f"创建于: {p['created_at'][:10] if p.get('created_at') else '-'}")
                with col3:
                    if p["status"] == "active":
                        if st.button("⏸ 暂停", key=f"pause_{kp}_{p['id']}"):
                            r = client.pause_plan(p["id"])
                            if r["code"] == 200:
                                st.rerun()
                            else:
                                st.error(r["message"])
                    elif p["status"] == "paused":
                        if st.button("▶ 继续", key=f"resume_{kp}_{p['id']}"):
                            r = client.resume_plan(p["id"])
                            if r["code"] == 200:
                                st.rerun()
                            else:
                                st.error(r["message"])

                # 展开查看每日任务
                with st.expander("查看每日任务", key=f"tasks_{kp}_{p['id']}"):
                    detail = client.get_plan(p["id"])
                    if detail["code"] != 200:
                        st.error(detail["message"])
                        continue

                    tasks = detail["data"].get("tasks", [])
                    if not tasks:
                        st.info("暂无任务数据。")
                        continue

                    for t in tasks:
                        task_status = t["status"]
                        status_icon = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}.get(task_status, "⬜")
                        ttype = t.get("task_type", "learn")
                        type_icon = {"learn": "📖", "weekly_review": "🔁", "monthly_review": "📚", "wrong_word_drill": "🎯"}.get(ttype, "📖")
                        type_label = {"learn": "学习日", "weekly_review": "周复习", "monthly_review": "月复习", "wrong_word_drill": "错题刷"}.get(ttype, ttype)
                        new_pct = t["completed_new"] / t["new_count"] if t["new_count"] > 0 else 1.0
                        rev_pct = t["completed_review"] / t["review_count"] if t["review_count"] > 0 else 1.0

                        with st.container(border=True):
                            st.markdown(f"{status_icon} {type_icon} **{t['task_date']}** · {type_label}")

                            if ttype == "learn":
                                col_new, col_rev = st.columns(2)
                                with col_new:
                                    st.progress(
                                        new_pct,
                                        text=f"新词 {t['completed_new']}/{t['new_count']}",
                                    )
                                with col_rev:
                                    st.progress(
                                        rev_pct,
                                        text=f"复习 {t['completed_review']}/{t['review_count']}",
                                    )
                            else:
                                # 周复习 / 月复习 / 错题刷：只有 review 槽
                                st.progress(
                                    rev_pct,
                                    text=f"复习 {t['completed_review']}/{t['review_count']}",
                                )

                            if task_status != "completed":
                                with st.expander("更新进度", key=f"upd_{kp}_{t['id']}"):
                                    cn = st.number_input(
                                        "已完成新词", min_value=0,
                                        max_value=t["new_count"], value=t["completed_new"],
                                        key=f"cn_{kp}_{t['id']}",
                                        disabled=(ttype != "learn"),
                                    )
                                    cr = st.number_input(
                                        "已完成复习", min_value=0,
                                        max_value=t["review_count"], value=t["completed_review"],
                                        key=f"cr_{kp}_{t['id']}",
                                    )
                                    if st.button("保存", key=f"save_{kp}_{t['id']}"):
                                        r = client.update_task(p["id"], t["id"], cn, cr)
                                        if r["code"] == 200:
                                            st.success("已更新")
                                            st.rerun()
                                        else:
                                            st.error(r["message"])
