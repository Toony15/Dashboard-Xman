import streamlit as st
import pandas as pd
import io
from dbConfig import get_db_connection
from google import genai
from dataManager import load_all_data
import locale
locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')

def compensation_page():
    st.title("Compensation")
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
        viewTable="calculated"
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
    quarter=["Q1", "Q2", "Q3", "Q4"]
    quarter = st.pills("Pilih Quarter", quarter, selection_mode="single", default="Q1")
    combined_df = combined_df[combined_df["quarter"]==quarter]
    
    st.header("Komponen Parameter")
    param1, param2, param3 = st.columns(3)
    
    with param1:
        paramLh = st.number_input(
            "Kontribusi Learning Hour", value=60, placeholder="Type a number...", key="input_param1"
        )
        st.write("The current number is ", 60)

    with param2:
        paramVariasi = st.number_input(
            "Variasi Penugasan", value=20, placeholder="Type a number...", key="input_param2"
        )
        st.write("The current number is ", 20)

    with param3:
        paramExpert = st.number_input(
            "Level Expert", value=20, placeholder="Type a number...", key="input_param3"
        )
        st.write("The current number is ", 20)

    st.header("Nominal Kompensasi")
    nominal = st.number_input(
        "Nominal Kompensasi (Rp)", value=None, placeholder="Masukkan nilai kompensasi...", key="input_param4"
    )

    st.header("Hasil Perhitungan")

    # --- 💡 Hitung skor per baris ---
    combined_df["skor"] = (
        combined_df["learning_hour"] * (paramLh / 100)
        + combined_df["variation"] * (paramVariasi / 100)
        + combined_df["expert_level"] * (paramExpert / 100)
    )

    # --- 💰 Hitung kompensasi per baris (jika nominal diberikan) ---
    if nominal:
        total_skor = combined_df["skor"].sum()
        combined_df["kompensasi"] = (combined_df["skor"] / total_skor) * nominal
    else:
        combined_df["kompensasi"] = 0

    # --- 💵 Format nilai Rupiah ---
    def format_rupiah(x):
        return f"Rp {x:,.0f}".replace(",", ".")

    # Format kolom nominal dan kompensasi
    formatted_df = combined_df.copy()
    formatted_df["kompensasi (Rp)"] = formatted_df["kompensasi"].apply(format_rupiah)

    # --- 🧾 Tampilkan hasil ---
    st.dataframe(
        formatted_df[["expert", "learning_hour", "variation", "expert_level", "skor", "kompensasi (Rp)"]],
        use_container_width=True
    )

    # Ringkasan hasil
    if nominal:
        st.success(f"✅ Total {len(combined_df)} baris data dihitung untuk {quarter} dengan total kompensasi {format_rupiah(nominal)}")
    else:
        st.info(f"ℹ️ Total {len(combined_df)} baris data dihitung untuk {quarter}, belum ada nominal kompensasi yang dimasukkan.")