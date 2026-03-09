import pandas as pd
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection

def learningHour():
    supabase = get_db_connection()

    def read_and_merge(files):
        all_data = []
        for uploaded_file in files:
            try:
                df = pd.read_excel(uploaded_file)
            except Exception as e:
                st.error(f"Gagal membaca file {uploaded_file.name}: {e}")
                continue
            file_name = uploaded_file.name.rsplit(".", 1)[0]
            parts = file_name.split("_")
            event, expert, unit, quarter = (parts + ["", "", "", ""])[:4]
            df["Event"] = event
            df["Expert"] = expert
            df["Unit"] = unit
            df["Quarter"] = quarter
            all_data.append(df)
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined["Event"] = combined["Event"].fillna("").astype(str).str.strip()
            return combined
        return pd.DataFrame()

    st.title("Learning Hours")
    options = ["Upload file", "From Data Base"]
    mode = st.pills("Data Resource", options, selection_mode="single", default="From Data Base")

    if mode == "Upload file":
        st.header("📁 Upload File")
        uploaded_files = st.file_uploader("Upload data (format Excel)", accept_multiple_files=True, type=["xls", "xlsx"])
        if uploaded_files:
            st.session_state["combined_df"] = read_and_merge(uploaded_files)
        combined_df = st.session_state.get("combined_df", pd.DataFrame())
    else:
        combined_df = load_all_data("learning_hour")

    if combined_df.empty:
        st.info("Tidak terdapat data")
        return

    st.dataframe(combined_df)

    quarters = ["Q1", "Q2", "Q3", "Q4"]
    quarter = st.pills("Pilih Quarter", quarters, selection_mode="single", default="Q1")
    
    if "quarter" in combined_df.columns:
        combined_df = combined_df[combined_df["quarter"] == quarter]
    elif "Quarter" in combined_df.columns:
        combined_df = combined_df[combined_df["Quarter"] == quarter]

    bobot_map = {
        "Coaching (Coach)": 1.5, 
        "Mentoring (Mentor)": 1.5, 
        "Expert Insight (Pembicara)": 1.3, 
        "Teaching": 1.4, 
        "Learning Content Designer/Developer": 1.5, 
        "Penguji/Assessor": 1.2, 
        "Self Learning": 1.0
    }

    if "variasi" not in combined_df.columns:
        st.warning("Kolom 'variasi' tidak ditemukan")
        return

    combined_df["bobot"] = combined_df["variasi"].map(bobot_map).fillna(1.0)
    combined_df["poin_lh"] = combined_df["learning_hour"] * combined_df["bobot"]
    
    total_poin_per_expert = combined_df.groupby("expert")["poin_lh"].sum().reset_index(name="total_poin")
    poin_tertinggi = total_poin_per_expert["total_poin"].max()
    
    combined_df = combined_df.merge(total_poin_per_expert, on="expert", how="left")
    combined_df["skor_lh"] = (combined_df["total_poin"] / poin_tertinggi) * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Learning Hour", combined_df["learning_hour"].sum(), border=True)
    col2.metric("Average Learning Hour", round(combined_df["learning_hour"].sum() / combined_df["expert"].nunique(), 2), border=True)
    col3.metric("Total Expert", combined_df["expert"].nunique(), border=True)

    st.subheader("📋 Detail Perhitungan Learning Hour")
    st.dataframe(combined_df[["nik", "expert", "learning_hour", "bobot", "poin_lh", "total_poin", "skor_lh"]])

    rekap_lh = combined_df.groupby(["nik", "expert"], as_index=False).agg({
        "learning_hour": "sum",
        "bobot": "first",
        "poin_lh": "sum",
        "skor_lh": "first"
    })
    rekap_lh["nik"] = rekap_lh["nik"].astype(int)
    rekap_lh = rekap_lh.sort_values(by="skor_lh", ascending=False).reset_index(drop=True)

    st.subheader("📊 Rekap Learning Hour Score per Expert (0-100)")
    st.dataframe(rekap_lh[["nik", "expert", "learning_hour", "bobot", "skor_lh"]], use_container_width=True)

    if st.button("💾 Simpan Learning Hour Score ke Database", key="btn_save_lh"):
        try:
            upload_df = rekap_lh[["nik", "expert", "skor_lh"]].copy()
            upload_df["quarter"] = quarter
            upload_df = upload_df.rename(columns={"skor_lh": "learning_hour"})

            count = 0
            for _, row in upload_df.iterrows():
                # Upsert - insert or update based on unique(nik, expert, quarter)
                supabase.table("calculated").upsert({
                    "nik": int(row["nik"]), 
                    "expert": row["expert"], 
                    "quarter": row["quarter"],
                    "learning_hour": float(row["learning_hour"])
                }).execute()
                count += 1

            st.success(f"✅ {count} data disimpan/diupdate untuk {quarter}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    learningHour()