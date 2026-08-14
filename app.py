import streamlit as st
import json
import time
import requests

# 1. Настройка страницы
st.set_page_config(page_title="Product Generator", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

# 2. CSS — исправленный, чтобы сайдбар был темным и не ломал верстку
CSS = """
<style>
/* Темный фон всего */
[data-testid="stAppViewContainer"], section[data-testid="stSidebar"] {
    background-color: #0e1117 !important;
}
/* Скрываем лишнее */
#MainMenu, header { visibility: hidden !important; }
/* Стилизация сайдбара */
section[data-testid="stSidebar"] { border-right: 1px solid #374151 !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# 3. Логика сессии (запоминание через session_state)
if "sb_token" not in st.session_state:
    st.session_state["sb_token"] = None

# ... (Тут остальной твой код: логика генерации, функции sb_login и т.д.) ...

# 4. Иконка сайта — она уже задана в page_icon="🤖" внутри set_page_config выше.
