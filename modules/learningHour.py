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
    mode = st.pills("Data Resource", options, selection_mode="single", default="Upload file")
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
        
