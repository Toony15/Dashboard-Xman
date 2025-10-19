import streamlit as st
import os
import pandas as pd

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
# --- Sidebar ---
with st.sidebar:
    st.logo("assets/xman.png", size="large")
    
    # st.title("ExmanComp")
    with st.container(horizontal=True, vertical_alignment="bottom", gap="small", horizontal_alignment="center"):
        logo1 = 'assets/corpu.jpeg'
        if os.path.exists(logo1):
            st.image(logo1, width=32)
        st.header("Telkom CorpU")
    st.link_button("Cek Dokumentasi", "https://www.openai.com")

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
                st.image(var, width=42)
                st.subheader("Variasi Penugasan")
            st.text("Keragaman jenis penugasan yang dijalankan expert pada periode program Knowledge Dissemination.")

st.markdown("""
                <style>
                div[data-baseweb="tab-list"] {
                    justify-content: space-between; /* Membagi tab secara merata */
                    width: 100%;
                }
                button[data-baseweb="tab"] {
                    flex: 1; /* Membuat tiap tab memiliki lebar sama */
                    max-width: 100%;
                }
                </style>
            """, unsafe_allow_html=True)
tab1, tab2, tab3= st.tabs(["Learning Hours", "Learning Impact", "Variasi Penugasan"])

with tab1:
    st.title("Parameter 1 - Kontribusi LH")

    # --- BAGIAN 1: Bobot Activity ---
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
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # --- BAGIAN 2: Contoh Scoring LH ---
    st.markdown("### 2. Contoh Scoring LH")

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
    st.title("Parameter 2 - Learning Impact")

    # --- Bagian 1: Deskripsi ---
    st.markdown(
        """
        **Contoh:** Penilaian peserta pelatihan terhadap **Expert A** dalam penugasan *Teaching*  
        <br>
        Hasil penilaian **LIM 1** peserta terhadap Expert A:
        """,
        unsafe_allow_html=True
    )

    # --- Bagian 2: Tabel Kriteria ---
    data = {
        "Kriteria": [
            "Berinteraksi dan berkomunikasi dengan peserta",
            "Manajemen Waktu",
            "Membantu memahami materi pelatihan",
            "Skor Rata-rata*",
        ],
        "Skala 1-10": [9, 8, 7, 8],
    }

    df = pd.DataFrame(data)

    # Tampilkan tabel
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    # --- Bagian 3: Hasil Perhitungan ---
    st.markdown(
        """
        <div style="
            text-align: center;
            background-color: #1E3A8A;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 18px;
            margin-top: 20px;
        ">
        <b>Poin Learning Impact terhadap Expert A:</b><br>
        = Skor rata-rata / 10 × 100 = 8 / 10 × 100 = <b>80</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- Catatan ---
    st.caption("*) Jumlah Peserta yang menilai (N) ≥ 10  \nPeserta yang tidak menilai tidak dihitung dalam skor rata-rata")

with tab3:
    st.title("Parameter 3 - Poin Variasi Penugasan")

    # --- Bagian 1: Deskripsi ---
    st.markdown("""
    **Contoh:**  
    Data **Variasi Penugasan Expert A** pada Q2 2025:
    """)

    # --- Data kiri: Variasi Penugasan ---
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

    # --- Data kanan: Perhitungan poin ---
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

    # Hitung total poin
    total_point = df_right["Total"].sum()

    # --- Layout dua kolom ---
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📋 Data Variasi Penugasan")
        st.dataframe(df_left, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### 🧮 Cara Hitung Poin Expert A")
        st.dataframe(df_right, use_container_width=True, hide_index=True)
        st.markdown(f"**Total Poin: {total_point:.1f}**")

    # --- Bagian hasil akhir ---
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

    # --- Catatan ---
    st.caption("*) Skor Parameter 3 = (Total Poin Expert / Total Poin Tertinggi) × 100  \n**) Minimal Total Poin Expert = 1.0")


# =================================================================================
st.divider()
with st.container(horizontal_alignment="center"):
    st.markdown(
        """
        <h1 style='text-align: center; color: white;'>
            Simulasi Compensation
        </h1>
        """,
        unsafe_allow_html=True
    )

# ========== 1️⃣ SKOR AKHIR EXPERT ==========
st.markdown("""
### 1. Skor Akhir Expert A:
= LH × 0.7 + Rating × 0.1 + Variasi × 0.2  
= 91.76 × 0.7 + 80 × 0.1 + 94.4 × 0.2  
= **91.1**
""")

# Data skor akhir
data_score = {
    "Expert": list("ABCDEFGHIJ") + ["Total"],
    "Poin Akhir": [91.1, 88.8, 85.1, 89.3, 90.5, 84.4, 86.7, 88.0, 83.9, 87.0, 874.8],
}
df_score = pd.DataFrame(data_score)

col1, col2 = st.columns([1, 1.2])

with col1:
    st.dataframe(df_score, use_container_width=True, hide_index=True)

# ========== 2️⃣ COMPENSATION EXPERT ==========
with col2:
    st.markdown("""
    ### 2. Compensation Expert A:
    = 91.1 / 874.8 × 45.000.000  
    = **4.686.214**
    """)

# ========== 3️⃣ BENEFIT & 4️⃣ LEVEL ==========
st.divider()

col3, col4 = st.columns(2)

with col3:
    st.markdown("### 3. Benefit Expert A:")
    benefit_data = {
        "Skor Akhir": ["70 – 79", "80 – 89", "90 – 100"],
        "Range": ["6 – 7 juta", "8 – 9 juta", "10 – 15 juta"],
        "Benefit": ["Sertifikasi Nasional", "Sertifikasi Internasional", "Sertifikasi Internasional"],
    }
    df_benefit = pd.DataFrame(benefit_data)
    st.dataframe(df_benefit, use_container_width=True, hide_index=True)

with col4:
    st.markdown("### 4. Expert Level:")
    level_data = {
        "Skor Akhir": ["70 – 79", "80 – 89", "90 – 100"],
        "Activeness": ["Q1", "Q1, Q2", "Q1, Q2, Q3, Q4"],
        "Level": ["Junior/Associate Expert", "Senior Expert", "Principal/Master Expert"],
    }
    df_level = pd.DataFrame(level_data)
    st.dataframe(df_level, use_container_width=True, hide_index=True)

# ========== FOOTNOTE ==========
st.markdown("""
<small>
*) Budget per Triwulan Rp 45.000.000  
**) Diprioritaskan sertifikasi Critical Competency
</small>
""", unsafe_allow_html=True)











