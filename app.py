import streamlit as st
import os

st.markdown(
            """
            <style>
            div[data-testid="stHorizontalBlock"] {
                background-color: #1f1f1f !important;
                border-radius: 10px;
                padding: 10px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
# st.set_page_config(
#     page_title="Expert Evaluation Dashboard",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# --- Sidebar ---
with st.sidebar:
    
    # st.title("ExmanComp")
    with st.container(horizontal=True, vertical_alignment="bottom", gap="small", horizontal_alignment="center"):
        logo1 = 'assets/corpu.jpeg'
        if os.path.exists(logo1):
            st.image(logo1, width=32)
        st.header("Expert Calculator")

    # try:
    #     col1, col2 = st.columns(2)
    #     with col1:
    #         logo1 = 'assets/Logo EXMAN Mentah.png'
    #         if os.path.exists(logo1):
    #             st.image(logo1, width=80)
    #     with col2:
    #         logo2 = 'assets/telkomcorpu_logo.png'
    #         if os.path.exists(logo2):
    #             st.image(logo2, width=80)
    # except Exception as e:
    #     st.write(f"Error loading logos: {e}")

st.set_page_config(
    page_title="Expert Evaluation Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.container(horizontal=True, vertical_alignment="bottom", gap="small", horizontal_alignment="center", border=True):
    logo1 = 'assets/xman.png'
    st.image(logo1, width=60)
    st.title("Expert Calculator", width="content")
    
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
