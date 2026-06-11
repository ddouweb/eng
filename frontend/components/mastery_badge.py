import streamlit as st

MASTERY_COLORS = {
    "unlearned": ("gray", "未学习"),
    "learning": ("orange", "学习中"),
    "familiar": ("blue", "熟悉"),
    "permanent": ("green", "永久记忆"),
}


def render(level: str | None, consecutive: int = 0, correct: int = 0, wrong: int = 0):
    if not level:
        level = "unlearned"
    color, label = MASTERY_COLORS.get(level, ("gray", level))
    st.badge(label, color=color)
    if correct + wrong > 0:
        st.caption(f"正确 {correct} / 错误 {wrong} | 连续正确 {consecutive}")
