import streamlit as st


def render(chinese: str, word_id: int) -> str | None:
    st.markdown(f"**中文：** {chinese}")
    answer = st.text_input("请输入英文拼写：", key=f"spell_{word_id}")
    if st.button("提交", key=f"spell_submit_{word_id}"):
        return answer.strip() if answer else ""
    return None
