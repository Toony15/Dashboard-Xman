# app.py
import streamlit as st
import pandas as pd
import io
from google import genai
import os

# Import modul halaman
from modules.satisfactionRate import satisfaction_page
from modules.learningHour import learning_hour_page
from modules.variation import variation_page
from modules.compensation import compensation_page
from dataManager import show_data_manager


# --- ⚙️ Konfigurasi Halaman ---
st.set_page_config(
    page_title="Expert Evaluation Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    # Tampilkan judul selalu agar tidak hilang ketika logo dimuat
    st.title("ExmanComp")

    try:
        # Tampilkan logo perusahaan di kiri atas (dikecilkan)
        col1, col2 = st.columns(2)
        with col1:
            logo1 = 'assets/Logo EXMAN Mentah.png'
            if os.path.exists(logo1):
                st.image(logo1, width=80)
            else:
                st.write("")  # placeholder jika tidak ada file
        with col2:
            logo2 = 'assets/telkomcorpu_logo.png'
            if os.path.exists(logo2):
                st.image(logo2, width=80)
            else:
                st.write("")
    except Exception as e:
        # Teks pengganti jika logo tidak bisa dimuat
        st.write(f"Error loading logos: {e}")
    
    st.header("Menu Utama")
    menu = st.radio(
        "Pilih Halaman:",
        ["Satisfaction", "Learning Hour", "Variation", "Compensation", "Data Manager"],
        label_visibility="collapsed"
    )

# --- 🚦 Routing Halaman ---
if menu == "Satisfaction":
    satisfaction_page()
elif menu == "Learning Hour":
    learning_hour_page()
elif menu == "Variation":
    variation_page()
elif menu == "Compensation":
    compensation_page()
elif menu == "Data Manager":
    show_data_manager()

