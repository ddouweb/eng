import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

st.set_page_config(page_title="家庭英语学习", page_icon="📚", layout="wide")
st.title("📚 Family English Coach")
st.markdown("上传教材图片 → 自动生成单词库 → 练习 → 追踪掌握进度")
