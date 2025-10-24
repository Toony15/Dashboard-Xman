import streamlit as st
import pandas as pd
import io
from dbConfig import get_db_connection
from google import genai
from dataManager import load_all_data

def expertLevel():
    st.title("Expert Level")  
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
    quarter=["Q1", "Q2", "Q3", "Q4"]
    quarter = st.pills("Pilih Quarter", quarter, selection_mode="single", default="Q1")
    expert_df = load_all_data("expertLevel")
    combined_df = combined_df[combined_df["quarter"]==quarter]
    main_df = combined_df[["expert", "company", "event", "variasi", "profLevel"]]
    
    main_df = main_df.merge(
        expert_df,
        how="left",              # semua baris combined_df tetap dipertahankan
        left_on="expert",        # kolom acuan di combined_df
        right_on="nama"          # kolom acuan di df_expert
    )

    # Ubah nama kolom level menjadi expert_level
    main_df.rename(columns={"level": "expert_level"}, inplace=True)

    # Hapus kolom 'nama' (jika tidak diperlukan lagi)
    main_df.drop(columns=["nama"], inplace=True)
    main_df.drop(columns=["id"], inplace=True)
    main_df["poin"] = main_df["profLevel"] * main_df["expert_level"]
    total_poin_per_expert = main_df.groupby("expert")["poin"].sum().reset_index(name="total_poin")
    poin_tertinggi = total_poin_per_expert["total_poin"].max()

    # Merge kembali ke combined_df
    main_df = main_df.merge(total_poin_per_expert, on="expert", how="left")
    
    # Tampilkan hasil
    st.dataframe(main_df)
    
    # rekap_expert = (
    #     main_df.groupby("expert", as_index=False)
    #     .agg({"poin": "sum"})
    #     .rename(columns={"poin_lh": "total_poin"})
    # )

    # # Hitung total poin tertinggi
    # poin_tertinggi = rekap_expert["total_poin"].max()

    # # Hitung skor normalisasi (seperti di formula)
    # rekap_expert["skor"] = (rekap_expert["total_poin"] / poin_tertinggi) * 100

    # # Urutkan dari skor tertinggi ke terendah
    # rekap_expert = rekap_expert.sort_values(by="skor", ascending=False).reset_index(drop=True)

    rekap = (
        main_df.groupby("expert", as_index=False)["poin"]
        .sum()
        .sort_values(by="poin", ascending=False)
    )
    rekap = rekap.rename(columns={
      "poin" : "poin_expert"   
    }
    )
    rekap["skor"] = round((rekap["poin_expert"] / poin_tertinggi) * 100,2)
    st.subheader("Rekap perhitungan Expert Level")
    st.dataframe(rekap)