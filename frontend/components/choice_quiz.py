import streamlit as st


def render(english: str, options: list[str], correct_answer: str, word_id: int) -> str | None:
    st.markdown(f"**{english}**")
    choice = st.radio("选择正确的中文释义：", options, key=f"choice_{word_id}")
    if st.button("确认", key=f"choice_submit_{word_id}"):
        return choice
    return None
