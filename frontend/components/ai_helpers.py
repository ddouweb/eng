"""Shared helpers for AI-powered features."""
import streamlit as st


def require_ai_key() -> bool:
    """Return True if AI API Key is configured; show warning otherwise."""
    if st.session_state.get("ai_api_key"):
        return True
    st.warning("请先在左侧栏配置 AI API Key")
    return False


def ai_kwargs() -> dict:
    """Return ai_provider + ai_api_key from session state for API calls."""
    return {
        "ai_provider": st.session_state.get("ai_provider"),
        "ai_api_key": st.session_state.get("ai_api_key"),
    }
