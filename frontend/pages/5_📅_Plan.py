import streamlit as st
from datetime import date
from api_client import client

st.header("📅 学习计划")

# ── 创建计划 ────────────────────────────────────────────
with st.expander("➕ 创建新计划", expanded=False):
    resp = client.list_units(page_size=100)
    if resp["code"] != 200:
        st.error(resp["message"])
        st.stop()

    units = resp["data"]["items"]
    if not units:
        st.info("还没有 Unit，请先添加单词。")
        st.stop()

    unit_options = {f"{u['title']} (ID:{u['id']})": u["id"] for u in units}

    name = st.text_input("计划名称", placeholder="例：三年级上册", key="plan_name")
    selected_keys = st.multiselect("选择 Unit", list(unit_options.keys()), key="plan_units")
    selected_ids = [unit_options[k] for k in selected_keys]
    daily_goal = st.number_input("每日目标（新词数）", min_value=1, max_value=200, value=15, key="plan_goal")
    deadline = st.date_input("截止日期（可选）", value=None, key="plan_deadline")

    if st.button("创建计划", disabled=not name or not selected_ids):
        deadline_str = str(deadline) if deadline else None
        resp = client.create_plan(
            name=name, daily_goal=daily_goal,
            unit_ids=selected_ids, deadline=deadline_str,
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
                    st.markdown(f"### {status_icon} {p['name']}")
                    st.caption(f"每日目标: {p['daily_goal']} 词 ｜ 截止: {p.get('deadline') or '未设置'}")
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
                        icon = {"completed": "✅", "in_progress": "🔄", "pending": "⬜"}.get(task_status, "⬜")
                        new_pct = t["completed_new"] / t["new_count"] if t["new_count"] > 0 else 1.0
                        rev_pct = t["completed_review"] / t["review_count"] if t["review_count"] > 0 else 1.0

                        with st.container(border=True):
                            st.markdown(f"{icon} **{t['task_date']}**")

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

                            if task_status != "completed":
                                with st.expander("更新进度", key=f"upd_{kp}_{t['id']}"):
                                    cn = st.number_input(
                                        "已完成新词", min_value=0,
                                        max_value=t["new_count"], value=t["completed_new"],
                                        key=f"cn_{kp}_{t['id']}",
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
