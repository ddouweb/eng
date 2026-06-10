import streamlit as st

MASTERY_COLORS = {
    "unlearned": ("#9CA3AF", "未学习"),
    "learning": ("#F97316", "学习中"),
    "familiar": ("#3B82F6", "熟悉"),
    "permanent": ("#22C55E", "永久记忆"),
}


def render(level: str | None, consecutive: int = 0, correct: int = 0, wrong: int = 0):
    if not level:
        level = "unlearned"
    color, label = MASTERY_COLORS.get(level, ("#9CA3AF", level))
    st.markdown(
        f'<span style="background:{color};color:white;padding:2px 10px;'
        f'border-radius:12px;font-size:0.85em;">{label}</span>',
        unsafe_allow_html=True,
    )
    if correct + wrong > 0:
        st.caption(f"正确 {correct} / 错误 {wrong} | 连续正确 {consecutive}")
