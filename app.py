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
        st.header("Telkom CorpU")

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
    
st.text("")
st.text("")
st.text("Expert Calculator adalah platform perhitungan digital yang dirancang untuk mendukung proses evaluasi dan pemberian kompensasi bagi para expert di lingkungan organisasi. Aplikasi ini mengolah data dari berbagai aspek seperti Learning Hours, Learning Impact, dan Variation untuk menghasilkan skor akhir yang mencerminkan kinerja serta kontribusi setiap individu secara objektif. Dengan sistem perhitungan otomatis yang mengacu pada pedoman Expert Management 2025, Expert Calculator membantu memastikan proses evaluasi berlangsung lebih transparan, efisien, dan adil. Melalui pendekatan berbasis data, platform ini juga mendukung pengambilan keputusan yang lebih akurat dalam pengelolaan reward dan pengembangan level expert di masa mendatang.")

st.text("")
st.text("")
with st.container(horizontal=True, gap="small"):
    
    with st.container(border=True, height=300):
        with st.container(horizontal=True):
            lh = 'assets/lh.png'
            st.image(lh, width=60)
            st.subheader("Learning Hours")
        st.text("Total realisasi jam kerja pembelajaran yang digunakan dalam penugasan Knowledge Dissemination (mengajar, content development, coaching, speaker, dsb.)")

    with st.container(border=True, height=300):
        with st.container(horizontal=True):
            imp = 'assets/imp.png'
            st.image(imp, width=60)
            st.subheader("Learning Impact")
        st.text("Hasil pengukuran efektivitas program pembelajaran yang mencerminkan sejauh mana kegiatan pembelajaran memberikan dampak positif. (LIM 1–Reaksi Peserta, LIM 2-Peningkatan Knowledge/Skill, LIM 3-Perubahan Perilaku, etc.)")
    with st.container(border=True, height=300):
            with st.container(horizontal=True):
                var = 'assets/var.png'
                st.image(var, width=60)
                st.subheader("Variasi Penugasan")
            st.text("Keragaman jenis penugasan yang dijalankan expert pada periode program Knowledge Dissemination.")








