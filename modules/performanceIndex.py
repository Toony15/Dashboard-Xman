import streamlit as st
import pandas as pd
import io
from dbConfig import get_db_connection
from google import genai
from dataManager import load_all_data

def performanceIndexPage():
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
    
    st.title("Performance Index")  
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
        viewTable="learningHour_new"
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

    # === Pilih Quarter terkini ===
    quarters = sorted(combined_df["Quarter"].dropna().unique())
    selected_quarter = st.selectbox("📆 Pilih Quarter (sebagai LH terkini):", quarters)

    # === Hitung total LH per Expert per Quarter ===
    lh_summary = (
        combined_df.groupby(["Expert", "Quarter"], as_index=False)["LH"]
        .sum()
        .pivot(index="Expert", columns="Quarter", values="LH")
        .fillna(0)
    )

    # Pastikan kolom quarter berurutan
    lh_summary = lh_summary.reindex(columns=sorted(lh_summary.columns))

    # === Hitung Performance Index ===
    # Ambil LH untuk quarter terkini
    lh_summary["LH_Terkini"] = lh_summary[selected_quarter]

    # Ambil rata-rata LH tiga quarter sebelumnya (jika ada)
    quarter_list = sorted(lh_summary.columns[:-1])  # semua quarter kecuali kolom 'LH_Terkini'
    if selected_quarter in quarter_list:
        current_idx = quarter_list.index(selected_quarter)
        prev_quarters = quarter_list[max(0, current_idx - 3):current_idx]
    else:
        prev_quarters = quarter_list[-3:]

    if prev_quarters:
        lh_summary["Rata2_LH_Sebelumnya"] = lh_summary[prev_quarters].mean(axis=1)
    else:
        lh_summary["Rata2_LH_Sebelumnya"] = 0

    # Hitung Performance Score (PI)
    lh_summary["Performance_Score"] = lh_summary["LH_Terkini"] / lh_summary["Rata2_LH_Sebelumnya"].replace(0, 1)
    
    #formula alternatif
    epsilon = 1  # konstanta kecil untuk menghindari pembagian nol
    alpha = 0.5  # bobot pertumbuhan
    beta = 0.5   # bobot kontribusi absolut

    lh_summary["New_Formula"] = (
        alpha * (lh_summary["LH_Terkini"] / (lh_summary["Rata2_LH_Sebelumnya"] + epsilon)) +
        beta * lh_summary["LH_Terkini"]
    )

    # Normalisasi skor PI (Skor PI = (PI / PI Maksimum) * 100)
    max_pi = lh_summary["Performance_Score"].max()
    lh_summary["Skor_PI"] = (lh_summary["Performance_Score"] / max_pi) * 100

    # === Tampilkan hasil ===
    st.subheader(f"📊 Performance Index untuk {selected_quarter}")
    st.dataframe(lh_summary.reset_index(), use_container_width=True)

    