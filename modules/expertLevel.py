import pandas as pd
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection

def expertLevel():
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

    st.title("Expert Level Score")

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

    main_df = combined_df[["nik", "expert", "company", "event", "variasi", "prof_level"]].copy()

    expert_df = load_all_data("expert_level")

    main_df = main_df.merge(
        expert_df[["nama", "level"]],
        how="left",
        left_on="expert",
        right_on="nama"
    )

    main_df.rename(columns={"level": "expert_level"}, inplace=True)
    main_df.drop(columns=["nama"], inplace=True)
    main_df["expert_level"] = main_df["expert_level"].fillna(0)

    def map_bobot_expert(level):
        if pd.isna(level) or level == 0:
            return 0
        elif level in [1, 2]:
            return 0
        elif level == 3:
            return 1.0
        elif level == 4:
            return 1.2
        elif level == 5:
            return 1.4
        else:
            return 0

    main_df["bobot_expert"] = main_df["expert_level"].apply(map_bobot_expert)

    def map_bobot_program(prof_level):
        if pd.isna(prof_level) or prof_level == 0:
            return 0
        elif prof_level in [1, 2]:
            return 1.0
        elif prof_level == 3:
            return 1.2
        elif prof_level >= 4:
            return 1.4
        else:
            return 0

    main_df["bobot_program"] = main_df["prof_level"].apply(map_bobot_program)

    total_bobot_program = main_df.groupby("expert")["bobot_program"].sum().reset_index(name="total_bobot_program")

    bobot_expert_per_expert = main_df.groupby("expert")[["bobot_expert"]].first().reset_index()

    poin_calc = total_bobot_program.merge(bobot_expert_per_expert, on="expert", how="left")
    poin_calc["poin_expert"] = poin_calc["total_bobot_program"] * poin_calc["bobot_expert"]

    main_df = main_df.merge(poin_calc[["expert", "poin_expert"]], on="expert", how="left")

    poin_tertinggi = poin_calc["poin_expert"].max()
    if poin_tertinggi == 0:
        poin_tertinggi = 1

    main_df["skor_expert"] = (main_df["poin_expert"] / poin_tertinggi) * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Training", len(main_df), border=True)
    col2.metric("Total Expert", main_df["expert"].nunique(), border=True)
    col3.metric("Max Expert Score", f"{poin_tertinggi:.2f}", border=True)

    st.subheader("📋 Detail Perhitungan Expert Level")
    display_cols = ["nik", "expert", "prof_level", "bobot_program", "expert_level", "bobot_expert", "poin_expert", "skor_expert"]
    st.dataframe(main_df[display_cols], use_container_width=True)

    rekap = poin_calc[["expert", "poin_expert"]].copy()

    nik_per_expert = main_df.groupby("expert")[["nik"]].first().reset_index()
    rekap = rekap.merge(nik_per_expert, on="expert", how="left")

    rekap = rekap[["nik", "expert", "poin_expert"]]
    rekap["skor_expert"] = ((rekap["poin_expert"] / poin_tertinggi) * 100).round(2)
    rekap = rekap.sort_values(by="poin_expert", ascending=False).reset_index(drop=True)

    rekap["nik"] = rekap["nik"].astype(int)

    st.subheader("📊 Rekap Expert Level Score per Expert (0-100)")
    st.dataframe(rekap[["nik", "expert", "skor_expert"]], use_container_width=True)

    if st.button("💾 Simpan Expert Level Score ke Database", key="btn_save_expert"):
        try:
            df_save = rekap[["nik", "expert", "skor_expert"]].copy()
            df_save["quarter"] = quarter
            df_save = df_save.rename(columns={"skor_expert": "expert_level"})

            inserted = 0
            updated = 0
            
            for _, row in df_save.iterrows():
                existing = supabase.table("calculated").select("id").eq("nik", int(row["nik"])).eq("expert", row["expert"]).eq("quarter", row["quarter"]).execute()
                
                if existing.data:
                    supabase.table("calculated").update({
                        "expert_level": float(row["expert_level"])
                    }).eq("nik", int(row["nik"])).eq("expert", row["expert"]).eq("quarter", row["quarter"]).execute()
                    updated += 1
                else:
                    supabase.table("calculated").insert({
                        "nik": int(row["nik"]),
                        "expert": row["expert"],
                        "quarter": row["quarter"],
                        "expert_level": float(row["expert_level"])
                    }).execute()
                    inserted += 1

            st.success(f"✅ {inserted} insert + {updated} update untuk {quarter}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    expertLevel()