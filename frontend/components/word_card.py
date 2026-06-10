import streamlit as st


def render(word: dict, show_answer: bool = False):
    col1, col2 = st.columns([3, 1])
    with col1:
        if show_answer:
            st.markdown(f"**{word['english']}**  →  {word['chinese']}")
        else:
            st.markdown(f"**{word['english']}**")

    with col2:
        tags = word.get("tags", [])
        tag_icons = {"favorite": "⭐", "high_freq": "🔥", "exam_focus": "📚", "excluded": "❌", "memorized": "✅"}
        icons = " ".join(tag_icons.get(t, "") for t in tags)
        if icons:
            st.markdown(icons)

    mastery = word.get("mastery")
    if mastery:
        from components.mastery_badge import render as badge
        badge(mastery["level"], mastery.get("consecutive_correct", 0),
              mastery.get("correct_count", 0), mastery.get("wrong_count", 0))
