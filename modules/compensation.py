import pandas as pd
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection
import locale

try:
    locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '')

def compensation():
    """
    Menghitung Compensation berdasarkan 3 komponen score:
    1. Learning Hour Score
    2. Variation Score
    3. Expert Level Score

    Formula:
    1. skor_akhir = (skor_lh ├ù param_lh + skor_variation ├ù param_variation + skor_expert ├ù param_expert) / 100
    2. kompensasi = (skor_akhir / total_skor_akhir) ├ù budget

    Dengan parameter yang bisa disesuaikan
    """

    supabase = get_db_connection()

    st.title("≡ƒÆ░ Compensation Calculator")

    # === LOAD DATA ===
    options = ["From Data Base"]
    mode = st.pills("Data Resource", options, selection_mode="single", default="From Data Base")

    viewTable = "calculated"
    combined_df = load_all_data(viewTable)

    if combined_df.empty:
        st.info("Tidak terdapat data di tabel 'calculated'. Pastikan sudah menjalankan perhitungan Learning Hour, Variation, dan Expert Level terlebih dahulu.")
        return None

    st.dataframe(combined_df)

    # === FILTER QUARTER ===
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    quarter = st.pills("Pilih Quarter", quarters, selection_mode="single", default="Q1")
    combined_df = combined_df[combined_df["quarter"] == quarter]

    # === PARAMETER SECTION ===
    st.header("ΓÜÖ∩╕Å Komponen Parameter")

    param_cols = st.columns(3)

    with param_cols[0]:
        param_lh = st.number_input(
            "≡ƒôÜ Kontribusi Learning Hour (%)",
            value=70,
            min_value=0,
            max_value=100,
            key="input_param_lh"
        )

    with param_cols[1]:
        param_variation = st.number_input(
            "≡ƒöä Variasi Penugasan (%)",
            value=20,
            min_value=0,
            max_value=100,
            key="input_param_variation"
        )

    with param_cols[2]:
        param_expert = st.number_input(
            "≡ƒæ¿ΓÇì≡ƒÆ╝ Level Expert (%)",
            value=10,
            min_value=0,
            max_value=100,
            key="input_param_expert"
        )

    # Validasi total parameter
    total_param = param_lh + param_variation + param_expert
    if total_param != 100:
        st.warning(f"ΓÜá∩╕Å Total parameter harus 100%, saat ini: {total_param}%")

    # === KOMPENSASI & FILTER SECTION ===
    comp_cols = st.columns(2)

    with comp_cols[0]:
        st.header("Nominal Kompensasi")
        budget = st.number_input(
            "Nominal Kompensasi Total (Rp)",
            value=None,
            min_value=0,
            placeholder="Masukkan total budget kompensasi...",
            key="input_budget"
        )

    with comp_cols[1]:
        st.header("Filter Learning Hour Minimal")
        min_lh = st.number_input(
            "Minimal Learning Hour per Quarter",
            value=10,
            min_value=0,
            key="input_min_lh"
        )

        # Filter data berdasarkan learning_hour minimal
        if "learning_hour" in combined_df.columns:
            combined_df = combined_df[combined_df["learning_hour"] >= min_lh].copy()

    # === EXCLUDE EXMAN ===
    exclude_nik = [860066, 910156, 730329]
    exclude_toggle = st.toggle("Exclude EXMAN (Exclude NIK tertentu)", value=False)

    if exclude_toggle:
        combined_df = combined_df[~combined_df["nik"].isin(exclude_nik)].copy()
        st.info("EXMAN telah dikecualikan dari perhitungan")

    # === VALIDASI KOLOM ===
    required_cols = ["nik", "expert", "learning_hour", "variation", "expert_level"]
    missing_cols = [col for col in required_cols if col not in combined_df.columns]

    if missing_cols:
        st.error(f"Kolom yang hilang: {missing_cols}")
        st.info(f"Data saat ini memiliki kolom: {combined_df.columns.tolist()}")
        return None

    # === STEP 1: PASTIKAN SEMUA KOLOM SCORE ADA DAN TIDAK NULL ===
    for col in ["learning_hour", "variation", "expert_level"]:
        if col not in combined_df.columns:
            st.warning(f"Kolom '{col}' tidak ditemukan. Isi dengan 0.")
            combined_df[col] = 0
        combined_df[col] = combined_df[col].fillna(0)

    # === STEP 2: HITUNG SKOR AKHIR ===
    combined_df["skor_akhir"] = (
        combined_df["learning_hour"] * (param_lh / 100) +
        combined_df["variation"] * (param_variation / 100) +
        combined_df["expert_level"] * (param_expert / 100)
    )

    # === STEP 3: HITUNG KOMPENSASI ===
    if budget and budget > 0:
        total_skor = combined_df["skor_akhir"].sum()

        if total_skor > 0:
            combined_df["kompensasi"] = (combined_df["skor_akhir"] / total_skor) * budget
        else:
            combined_df["kompensasi"] = 0
            st.warning("ΓÜá∩╕Å Total skor adalah 0, tidak bisa menghitung kompensasi")
    else:
        combined_df["kompensasi"] = 0
        st.info("Masukkan nominal kompensasi untuk melihat distribusi kompensasi")

    # === FORMAT RUPIAH ===
    def format_rupiah(x):
        return f"Rp {x:,.0f}".replace(",", ".")

    # === RINGKASAN HASIL ===
    st.header("Hasil Perhitungan Compensation")

    summary_cols = st.columns(4)

    with summary_cols[0]:
        st.metric("Total Expert", len(combined_df), border=True)

    with summary_cols[1]:
        st.metric("Total Skor Akhir", f"{combined_df['skor_akhir'].sum():.2f}", border=True)

    with summary_cols[2]:
        if budget:
            st.metric("Total Budget", format_rupiah(budget), border=True)
        else:
            st.metric("Total Budget", "Rp 0", border=True)

    with summary_cols[3]:
        if budget and len(combined_df) > 0:
            avg_comp = combined_df["kompensasi"].sum() / len(combined_df)
            st.metric("Rata-rata Kompensasi", format_rupiah(avg_comp), border=True)
        else:
            st.metric("Rata-rata Kompensasi", "Rp 0", border=True)

    # === PREPARE DISPLAY DATAFRAME ===
    display_df = combined_df.copy()
    display_df["kompensasi (Rp)"] = display_df["kompensasi"].apply(format_rupiah)

    # === TAMPILKAN DETAIL PERHITUNGAN ===
    st.subheader("Detail Perhitungan Kompensasi per Expert")

    display_cols = [
        "nik", "expert", "learning_hour", "variation", "expert_level",
        "skor_akhir", "kompensasi (Rp)"
    ]

    st.dataframe(display_df[display_cols], use_container_width=True)

    # === TAMBAHAN: SUMMARY STATISTIK ===
    st.subheader("Statistik Kompensasi")

    stats_cols = st.columns(3)

    with stats_cols[0]:
        st.metric("Kompensasi Tertinggi",
                 format_rupiah(combined_df["kompensasi"].max()) if budget else "Rp 0",
                 border=True)

    with stats_cols[1]:
        st.metric("Kompensasi Terendah",
                 format_rupiah(combined_df["kompensasi"].min()) if budget else "Rp 0",
                 border=True)

    with stats_cols[2]:
        if budget and len(combined_df) > 0:
            std_comp = combined_df["kompensasi"].std()
            st.metric("Std Deviation Kompensasi",
                     format_rupiah(std_comp),
                     border=True)

    # === DOWNLOAD EXCEL ===
    if st.button("Download Hasil Kompensasi (Excel)", key="btn_download_comp"):
        # Prepare download dataframe
        download_df = display_df[[
            "nik", "expert", "quarter",
            "learning_hour", "variation", "expert_level",
            "skor_akhir", "kompensasi"
        ]].copy()

        # Convert to Excel
        import io
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            download_df.to_excel(writer, sheet_name="Kompensasi", index=False)

        buffer.seek(0)

        st.download_button(
            label="Download Kompensasi.xlsx",
            data=buffer,
            file_name=f"Kompensasi_{quarter}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return combined_df


if __name__ == "__main__":
    compensation()