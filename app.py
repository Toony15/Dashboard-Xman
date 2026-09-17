import streamlit as st
import os
import pandas as pd
from modules.learningHour import learningHour
from modules.variation import variation_page
from modules.expertLevel import expertLevel
from modules.compensation import compensation

# === STREAMLIT CONFIG ===
st.set_page_config(
    page_title="Expert Evaluation Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === CUSTOM STYLING ===
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

# === SIDEBAR ===
with st.sidebar:
    st.logo("assets/xman.png", size="large") if os.path.exists("assets/xman.png") else None
    
    with st.container(horizontal=True, vertical_alignment="bottom", gap="small", horizontal_alignment="center"):
        logo1 = 'assets/corpu.jpeg'
        if os.path.exists(logo1):
            st.image(logo1, width=32)
        st.header("Telkom CorpU")
    
    st.link_button("Cek Dokumentasi", "https://www.openai.com")
    st.markdown("---")
    
    menu_options = [
        "🏠 Dashboard",
        "📚 Learning Hour Score",
        "🔄 Variation Score",
        "👨‍💼 Expert Level Score",
        "💰 Compensation"
    ]
    
    selected_menu = st.radio("Pilih Menu", menu_options)

# === HEADER ===
with st.container(horizontal=True, vertical_alignment="bottom", gap="small", horizontal_alignment="center", border=True):
    logo1 = 'assets/xman.png'
    if os.path.exists(logo1):
        st.image(logo1, width=60)
    st.title("Expert Calculator", width="content")

# === PAGE ROUTING ===
if selected_menu == "🏠 Dashboard":
    st.text("")
    st.text("")
    st.text("Expert Calculator adalah platform perhitungan digital yang dirancang untuk mendukung proses evaluasi dan pemberian kompensasi bagi para expert di lingkungan organisasi. Aplikasi ini mengolah data dari berbagai aspek seperti Learning Hours, Learning Impact, dan Variation untuk menghasilkan skor akhir yang mencerminkan kinerja serta kontribusi setiap individu secara objektif. Dengan sistem perhitungan otomatis yang mengacu pada pedoman Expert Management 2025, Expert Calculator membantu memastikan proses evaluasi berlangsung lebih transparan, efisien, dan adil. Melalui pendekatan berbasis data, platform ini juga mendukung pengambilan keputusan yang lebih akurat dalam pengelolaan reward dan pengembangan level expert di masa mendatang.")
    
    st.text("")
    st.text("")
    
    with st.container(horizontal=True, gap="small"):
        with st.container(border=True, height=300):
            with st.container(horizontal=True):
                lh = 'assets/lh.png'
                if os.path.exists(lh):
                    st.image(lh, width=60)
                st.subheader("Learning Hours")
            st.text("Total realisasi jam kerja pembelajaran yang digunakan dalam penugasan Knowledge Dissemination (mengajar, content development, coaching, speaker, dsb.)")

        with st.container(border=True, height=300):
            with st.container(horizontal=True):
                imp = 'assets/imp.png'
                if os.path.exists(imp):
                    st.image(imp, width=60)
                st.subheader("Learning Impact")
            st.text("Hasil pengukuran efektivitas program pembelajaran yang mencerminkan sejauh mana kegiatan pembelajaran memberikan dampak positif. (LIM 1–Reaksi Peserta, LIM 2-Peningkatan Knowledge/Skill, LIM 3-Perubahan Perilaku, etc.)")
        
        with st.container(border=True, height=300):
            with st.container(horizontal=True):
                var = 'assets/var.png'
                if os.path.exists(var):
                    st.image(var, width=42)
                st.subheader("Variasi Penugasan")
            st.text("Keragaman jenis penugasan yang dijalankan expert pada periode program Knowledge Dissemination.")

elif selected_menu == "📚 Learning Hour Score":
    st.markdown("""
        <style>
        div[data-baseweb="tab-list"] {
            justify-content: space-between;
            width: 100%;
        }
        button[data-baseweb="tab"] {
            flex: 1;
            max-width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📖 Panduan", "🧮 Kalkulator"])
    
    with tab1:
        st.title("Parameter 1 - Kontribusi Learning Hour")
        
        st.markdown("### 1. Bobot Activity")
        
        data = {
            "No": [1, 2, 3, 4, 5, 6],
            "Assignment": [
                "Coaching (Coach)/Mentoring (Mentor)",
                "Expert Insight (Pembicara)",
                "Teaching",
                "Learning Content Designer/Developer",
                "Publikasi Artikel/Video/Podcast",
                "Penguji/Assessor",
            ],
            "Bobot": [1.5, 1.3, 1.4, 1.5, 1.1, 1.2],
            "Dasar": [
                "personalized, high-impact, consistent",
                "exposed, representasi",
                "Knowledge delivery",
                "One way",
                "Individual",
                "Assessment & validation",
            ],
        }
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.divider()
        
        st.markdown("### 2. Contoh Scoring Learning Hour")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🧑‍🏫 Expert A di Q2 2025")
            st.markdown("""
            **Teaching             :** 10 LH  
            **Content Development  :** 8 LH  
            **Speaker              :** 4 LH  
            
            **Perhitungan:**  
            10 × 1.4 + 8 × 1.5 + 4 × 1.3 = **31.2**
            """)
        
        with col2:
            st.markdown("#### 👨‍💻 Expert B di Q2 2025")
            st.markdown("""
            **Teaching:** 8 LH  
            **Content Development:** 10 LH  
            **Speaker:** 6 LH  
            
            **Perhitungan:**  
            8 × 1.4 + 10 × 1.5 + 6 × 1.3 = **34**
            """)
        
        st.markdown("""
        <div style='text-align: center; background-color: #1E3A8A; color: white; padding: 15px; border-radius: 8px; font-size: 18px;'>
        <b>Skor Expert A = (31.2 / 34) × 100 = 91.76</b>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("Skor Normalisasi = (Poin Aktual / Poin Tertinggi) × 100")
    
    with tab2:
        learningHour()

elif selected_menu == "🔄 Variation Score":
    st.markdown("""
        <style>
        div[data-baseweb="tab-list"] {
            justify-content: space-between;
            width: 100%;
        }
        button[data-baseweb="tab"] {
            flex: 1;
            max-width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📖 Panduan", "🧮 Kalkulator"])
    
    with tab1:
        st.title("Parameter 3 - Poin Variasi Penugasan")
        
        st.markdown("""
        **Contoh:**  
        Data **Variasi Penugasan Expert A** pada Q2 2025:
        """)
        
        data_right = {
            "No": [1, 2, 3, 4, 5, 6],
            "Jenis Penugasan": [
                "Coach",
                "Mentor",
                "Speaker",
                "Teaching",
                "Content Development",
                "Publikasi Artikel",
            ],
            "Frekuensi": [3, 5, 4, 4, 1, 1],
            "Bobot": [1.5, 1.4, 1.3, 1.2, 1.1, 1.0],
        }
        df_right = pd.DataFrame(data_right)
        df_right["Total"] = df_right["Frekuensi"] * df_right["Bobot"]
        
        total_point = df_right["Total"].sum()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📋 Data Variasi Penugasan")
            data_left = {
                "No": [1, 2, 3, 4, 5, 6],
                "Jenis Penugasan": [
                    "Coach",
                    "Mentor",
                    "Speaker",
                    "Teaching",
                    "Content Development",
                    "Publikasi Artikel",
                ],
                "Frekuensi": [3, 5, 4, 4, 1, 1],
            }
            df_left = pd.DataFrame(data_left)
            st.dataframe(df_left, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("#### 🧮 Cara Hitung Poin Expert A")
            st.dataframe(df_right, use_container_width=True, hide_index=True)
            st.markdown(f"**Total Poin: {total_point:.1f}**")
        
        max_point = 25
        score = (total_point / max_point) * 100
        
        st.markdown(
            f"""
            <div style="
                text-align: center;
                background-color: #1E3A8A;
                color: white;
                padding: 15px;
                border-radius: 8px;
                font-size: 18px;
                margin-top: 25px;
            ">
            Misal Total Poin Tertinggi = {max_point}  
            <br>
            Skor Expert A = {total_point:.1f} / {max_point} × 100 = <b>{score:.1f}</b>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.caption("*) Skor Parameter 3 = (Total Poin Expert / Total Poin Tertinggi) × 100  \n**) Minimal Total Poin Expert = 1.0")
    
    with tab2:
        variation_page()

elif selected_menu == "👨‍💼 Expert Level Score":
    expertLevel()

elif selected_menu == "💰 Compensation":
    compensation()

# === FOOTER ===
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
    <p>Expert Calculator v1.0 | Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)