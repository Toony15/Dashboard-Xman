import streamlit as st
import os

st.set_page_config(
    page_title="Expert Evaluation Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Sidebar ---
with st.sidebar:
    st.title("ExmanComp")

    try:
        col1, col2 = st.columns(2)
        with col1:
            logo1 = 'assets/Logo EXMAN Mentah.png'
            if os.path.exists(logo1):
                st.image(logo1, width=80)
        with col2:
            logo2 = 'assets/telkomcorpu_logo.png'
            if os.path.exists(logo2):
                st.image(logo2, width=80)
    except Exception as e:
        st.write(f"Error loading logos: {e}")

st.title("📊 Expert Evaluation Dashboard")
st.markdown(
    """
    Selamat datang di **ExmanComp Dashboard** 👋  
    Pilih halaman di sidebar untuk mulai menavigasi:
    - Learning Impact 1  
    - Learning Hour  
    - Variation  
    - Compensation  
    - Data Manager  
    """
)
