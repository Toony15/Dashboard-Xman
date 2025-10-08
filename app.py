# app.py
import streamlit as st
import streamlit as st
import pandas as pd
import io
from google import genai

# Import modul halaman
from modules.satisfactionRate import satisfaction_page
from modules.learningHour import learning_hour_page
from modules.variation import variation_page
from modules.compensation import compensation_page

# --- 🎛️ Sidebar Menu ---
st.sidebar.title("📁 Menu Utama")
menu = st.sidebar.radio(
    "Pilih Halaman:",
    ["Satisfaction", "Learning Hour", "Variation", "Compensation"]
)

# --- Routing Halaman ---
if menu == "Satisfaction":
    satisfaction_page()
elif menu == "Learning Hour":
    learning_hour_page()
elif menu == "Variation":
    variation_page()
elif menu == "Compensation":
    compensation_page()
