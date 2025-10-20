import streamlit as st
import pandas as pd
import io
from dbConfig import get_db_connection
from google import genai
from dataManager import load_all_data

def learning_hour_page():
    supabase = get_db_connection()
    def read_and_merge(files):
        all_data = []
        for uploaded_file in files:
            try:
                df = pd.read_excel(uploaded_file)
            except Exception as e:
                st.error(f"Gagal membaca file {uploaded_file.name}: {e}")
                continue
            # Ambil nama file tanpa ekstensi
            file_name = uploaded_file.name.rsplit(".", 1)[0]
            parts = file_name.split("_")
            event, expert, unit,quarter = (parts + ["", "", "", ""])[:4]

            # Tambahkan kolom metadata
            df["Event"] = event
            df["Expert"] = expert
            df["Unit"] = unit
            df["Quarter"] = quarter
            all_data.append(df)

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined["Event"] = combined["Event"].fillna("").astype(str).str.strip()
            return combined
        else:
            return pd.DataFrame()
    
    st.title("Learning Hours")  
    options = ["Upload file","From Data Base"]
    mode = st.pills("Data Resource", options, selection_mode="single", default="From Data Base")
    if mode == "Upload file":   
        st.header("📊 Upload File")

        uploaded_files = st.file_uploader(
            "Upload data (format Excel)", 
            accept_multiple_files=True, 
            type=["xls", "xlsx"]
        )
        # Simpan hasil upload ke session_state agar tidak hilang setelah interaksi
        if uploaded_files:
            st.session_state["combined_df"] = read_and_merge(uploaded_files)
        # Ambil data dari session_state
        combined_df = st.session_state.get("combined_df", pd.DataFrame())
    elif mode == "From Data Base":
        viewTable="learningHour"
        combined_df = load_all_data(viewTable)
    if combined_df.empty:
        st.info("Tidak terdapat data")
    else:
        # st.success(f"✅ Data berhasil digabungkan ({len(combined_df)} baris total)")
        st.dataframe(combined_df)
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
    st.empty
    filter=["All", "LIM 1"]
    filter = st.pills("Filter", filter, selection_mode="single", default="All")
    if filter == "LIM 1":
        event_df = load_all_data("learningImpact1")
        unique_events = event_df["Event"].dropna().unique().tolist()
        st.write("📅 Daftar Event LIM 1:")
        unique_events_df = pd.DataFrame({
            "Event": unique_events
        })
        unique_events_df.index = range(1, len(unique_events_df) + 1)
        unique_events_df.index.name = "No"
        st.dataframe(unique_events_df, use_container_width=True)
        valid_events = unique_events_df["Event"].unique()
        # Filter combined_df agar hanya berisi event yang ada di unique_events_df
        combined_df = combined_df[combined_df["Event"].isin(valid_events)].reset_index(drop=True)

    quarter=["Q1", "Q2", "Q3", "Q4"]
    quarter = st.pills("Pilih Quarter", quarter, selection_mode="single", default="Q1")
    combined_df = combined_df[combined_df["Quarter"]==quarter]

    # Mapping bobot berdasarkan kolom Variasi
    bobot_map = {
        "Coaching (Coach)/Mentoring (Mentor)": 1.5,
        "Expert Insight (Pembicara)": 1.3,
        "Teaching": 1.4,
        "Learning Content Designer/Developer": 1.5,
        "Publikasi Artikel/Video/Podcast": 1.1,
        "Penguji/Assessor": 1.2
    }

    # 1️⃣ Tambahkan kolom bobot berdasarkan Variasi
    combined_df["bobot"] = combined_df["Variasi"].map(bobot_map)

    # 2️⃣ Hitung kolom poin_lh
    combined_df["poin_lh"] = combined_df["LH"] * combined_df["bobot"]

    # 3️⃣ Hitung total poin tertinggi antar expert
    total_poin_per_expert = combined_df.groupby("Expert")["poin_lh"].sum().reset_index(name="total_poin")
    poin_tertinggi = total_poin_per_expert["total_poin"].max()

    # 4️⃣ Merge kembali ke combined_df
    combined_df = combined_df.merge(total_poin_per_expert, on="Expert", how="left")

    # 5️⃣ Hitung skor normalisasi
    combined_df["skor"] = (combined_df["total_poin"] / poin_tertinggi) * 100

    # 6️⃣ Tampilkan hasil
    st.dataframe(combined_df[["Expert", "Event", "Variasi", "LH", "bobot", "poin_lh", "total_poin", "skor"]])
    
    # === 🔹 Buat DataFrame Rekap per Expert ===
    rekap_expert = (
        combined_df.groupby("Expert", as_index=False)
        .agg({"poin_lh": "sum"})
        .rename(columns={"poin_lh": "total_poin"})
    )

    # Hitung total poin tertinggi
    poin_tertinggi = rekap_expert["total_poin"].max()

    # Hitung skor normalisasi (seperti di formula)
    rekap_expert["skor"] = (rekap_expert["total_poin"] / poin_tertinggi) * 100

    # Urutkan dari skor tertinggi ke terendah
    rekap_expert = rekap_expert.sort_values(by="skor", ascending=False).reset_index(drop=True)

    # === 🔹 Tampilkan hasil rekap ===
    st.subheader("📋 Rekap Total Poin & Skor per Expert")
    st.dataframe(rekap_expert, use_container_width=True)


        
