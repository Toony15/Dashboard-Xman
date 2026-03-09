import pandas as pd
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection

def newVariation():
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

    st.title("Variation Score")

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

    # === DEFINE TARGET VARIATIONS DULU ===
    target_variations = [
        "Coaching (Coach)/Mentoring (Mentor)",
        "Expert Insight (Pembicara)",
        "Teaching",
        "Learning Content Designer/Developer",
        "Penguji/Assessor",
        "Self Learning"
    ]

    # === DEBUG ===
    st.subheader("🔍 Debug: Cek Variasi yang Ada")
    st.write("Unique variasi values:")
    st.write(combined_df["variasi"].unique())
    
    missing = combined_df[~combined_df["variasi"].isin(target_variations)]
    st.write("Variasi yang tidak match target:")
    st.write(missing["variasi"].unique())

    # === CEK EXPERT YANG MISSING ===
    st.subheader("⚠️ Expert yang MISSING di Variation")
    learning_hour_df = load_all_data("learning_hour")
    learning_hour_experts = learning_hour_df.groupby(["nik", "expert"]).size().reset_index(name="count")[["nik", "expert"]]
    variation_experts = combined_df[combined_df["variasi"].isin(target_variations)].groupby(["nik", "expert"]).size().reset_index(name="count")[["nik", "expert"]]
    missing_experts = learning_hour_experts[~learning_hour_experts[["nik", "expert"]].apply(tuple, 1).isin(variation_experts[["nik", "expert"]].apply(tuple, 1))]
    
    # === CEK VARIASI DARI MISSING EXPERTS ===
    st.subheader("📊 Variasi dari 34 Expert MISSING")

    missing_niks = missing_experts["nik"].unique()
    missing_data = combined_df[combined_df["nik"].isin(missing_niks)]

    st.write("Variasi apa yang dimiliki 34 expert missing:")
    st.write(missing_data["variasi"].unique())

    st.write("\nDetail 34 expert missing:")
    st.dataframe(missing_data[["nik", "expert", "variasi"]].drop_duplicates())

    st.write(f"Total expert di Learning Hour: {len(learning_hour_experts)}")
    st.write(f"Total expert di Variation: {len(variation_experts)}")
    st.write(f"Total expert MISSING: {len(missing_experts)}")
    if len(missing_experts) > 0:
        st.dataframe(missing_experts)
    else:
        st.info("Semua expert ada ✅")


    quarters = ["Q1", "Q2", "Q3", "Q4"]
    quarter = st.pills("Pilih Quarter", quarters, selection_mode="single", default="Q1")

    if "quarter" in combined_df.columns:
        combined_df = combined_df[combined_df["quarter"] == quarter]
    elif "Quarter" in combined_df.columns:
        combined_df = combined_df[combined_df["Quarter"] == quarter]

    target_variations = [
        "Coaching (Coach)/Mentoring (Mentor)",
        "Expert Insight (Pembicara)",
        "Teaching",
        "Learning Content Designer/Developer",
        "Penguji/Assessor",
        "Self Learning"
    ]

    bobot_map = {
        "Coaching (Coach)/Mentoring (Mentor)": 1.5,
        "Expert Insight (Pembicara)": 1.3,
        "Teaching": 1.4,
        "Learning Content Designer/Developer": 1.5,
        "Penguji/Assessor": 1.2,
        "Self Learning": 1.0
    }

    if "variasi" not in combined_df.columns:
        st.warning("Kolom 'variasi' tidak ditemukan")
        return

    rekap_variation = (
        combined_df[combined_df["variasi"].isin(target_variations)]
        .groupby(["nik", "expert", "variasi"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    for var in target_variations:
        if var not in rekap_variation.columns:
            rekap_variation[var] = 0

    rekap_variation["total_poin_variation"] = sum(
        rekap_variation[col] * bobot_map.get(col, 0)
        for col in target_variations
    )

    max_poin = rekap_variation["total_poin_variation"].max()
    if max_poin > 0:
        rekap_variation["skor_variation"] = (rekap_variation["total_poin_variation"] / max_poin * 100).round(2)
    else:
        rekap_variation["skor_variation"] = 0

    rekap_variation["nik"] = rekap_variation["nik"].astype(int)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Penugasan", len(combined_df), border=True)
    col2.metric("Total Expert", rekap_variation["expert"].nunique(), border=True)
    col3.metric("Max Variation Score", f"{max_poin:.2f}", border=True)

    st.subheader("📋 Detail Frekuensi Variasi per Expert")
    display_cols = ["nik", "expert"] + target_variations + ["total_poin_variation", "skor_variation"]
    st.dataframe(rekap_variation[display_cols], use_container_width=True)

    rekap_summary = rekap_variation[["nik", "expert", "skor_variation"]].copy()
    rekap_summary = rekap_summary.sort_values(by="skor_variation", ascending=False).reset_index(drop=True)

    st.subheader("📊 Rekap Variation Score per Expert (0-100)")
    st.dataframe(rekap_summary[["nik", "expert", "skor_variation"]], use_container_width=True)

    if st.button("💾 Simpan Variation Score ke Database", key="btn_save_variation"):
        try:
            upload_df = rekap_summary[["nik", "expert", "skor_variation"]].copy()
            upload_df["quarter"] = quarter
            upload_df = upload_df.rename(columns={"skor_variation": "variation"})

            updated = 0
            for _, row in upload_df.iterrows():
                supabase.table("calculated").update({
                    "variation": float(row["variation"])
                }).eq("nik", int(row["nik"])).eq("expert", row["expert"]).eq("quarter", row["quarter"]).execute()
                updated += 1

            st.success(f"✅ {updated} data diupdate untuk {quarter}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


if __name__ == "__main__":
    newVariation()