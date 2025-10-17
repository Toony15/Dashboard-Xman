import streamlit as st
import pandas as pd
import io

# Halaman Variation - hitung poin variasi penugasan per teori (lihat slide)
def _find_column(df, candidates):
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    # try fuzzy contains
    for col in df.columns:
        low = col.lower()
        for cand in candidates:
            if cand.lower() in low:
                return col
    return None

def _normalize_assignment(name):
    if not isinstance(name, str):
        return "Other"
    s = name.lower()
    if "coach" in s:
        return "Coach"
    if "mentor" in s or "mentoring" in s:
        return "Mentor"
    if "speaker" in s:
        return "Speaker"
    if "teach" in s:
        return "Teaching"
    if "content" in s:
        return "Content Development"
    if "publikas" in s or "artikel" in s or "publication" in s or "article" in s:
        return "Publikasi Artikel"
    return name.strip().title()

# bobot per jenis sesuai contoh slide
BOBOT_MAP = {
    "Coach": 1.5,
    "Mentor": 1.4,
    "Speaker": 1.3,
    "Teaching": 1.2,
    "Content Development": 1.1,
    "Publikasi Artikel": 1.0
}

def variation_page():
    st.title("Parameter 3 — Poin Variasi Penugasan")
    st.write("Unggah file Excel (sheet berisi kolom NIK/NAME/Variasi Penugasan/FREKUENSI atau serupa).")

    uploaded = st.file_uploader("Upload data variasi (XLSX/XLS)", type=["xlsx", "xls"])
    if uploaded is None:
        st.info("Silakan unggah file Excel untuk memulai.")
        return

    try:
        df = pd.read_excel(uploaded, sheet_name=0)
    except Exception as e:
        st.error(f"Error membaca file Excel: {e}")
        return

    st.subheader("Preview data mentah")
    st.dataframe(df.head())

    # deteksi kolom penting
    col_nik = _find_column(df, ["NIK", "nik", "Id", "ID"])
    col_name = _find_column(df, ["NAME", "Name", "Nama"])
    col_variasi = _find_column(df, ["Variasi Penugasan", "Variasi", "Sub Penugasan", "Jenis Penugasan"])
    col_freq = _find_column(df, ["FREKUENSI", "Frequency", "Freq", "Jumlah"])

    if not (col_nik and col_name and col_variasi and col_freq):
        st.warning("Tidak menemukan semua kolom wajib. Diperlukan kolom NIK, NAME, Variasi Penugasan, dan FREKUENSI (nama kolom fleksibel).")
        st.write(dict(detected_columns={
            "nik": col_nik, "name": col_name, "variasi": col_variasi, "freq": col_freq
        }))
        return

    working = df[[col_nik, col_name, col_variasi, col_freq]].copy()
    working.columns = ["NIK", "NAME", "VARIASI_RAW", "FREQ"]
    # bersihkan dan normalisasi
    working["FREQ"] = pd.to_numeric(working["FREQ"], errors="coerce").fillna(0).astype(float)
    working["VARIASI"] = working["VARIASI_RAW"].apply(_normalize_assignment)
    # tentukan bobot dari map; jika tidak ada, pakai 1.0 (atau bisa ditampilkan untuk review)
    working["BOBOT"] = working["VARIASI"].map(BOBOT_MAP).fillna(1.0)
    working["POINT"] = working["FREQ"] * working["BOBOT"]

    st.subheader("Detail per penugasan")
    st.dataframe(working.head(200))

    # ringkasan per expert
    summary = (
        working
        .groupby(["NIK", "NAME", "VARIASI", "BOBOT"], as_index=False)
        .agg({"FREQ": "sum", "POINT": "sum"})
        .sort_values(["NIK", "VARIASI"])
    )

    per_expert = (
        summary
        .groupby(["NIK", "NAME"], as_index=False)
        .agg(total_point=("POINT", "sum"))
        .sort_values("total_point", ascending=False)
    )

    st.subheader("Ringkasan per Expert (Total Point)")
    st.dataframe(per_expert)

    max_point = st.number_input("Total Point Tertinggi (untuk normalisasi skor)", value=25.0, step=1.0)
    min_total_point = st.number_input("Minimal Total Point Expert (batas bawah)", value=1.0, step=0.1)

    per_expert["total_point_clamped"] = per_expert["total_point"].apply(lambda v: max(v, min_total_point))
    per_expert["score_percent"] = (per_expert["total_point_clamped"] / float(max_point)) * 100
    per_expert["score_percent"] = per_expert["score_percent"].clip(0, 100).round(2)

    st.subheader("Skor Normalisasi (Top 10)")
    st.dataframe(per_expert.sort_values("total_point", ascending=False).head(10))

    st.markdown("Download hasil ringkasan:")
    csv = per_expert.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV summary", data=csv, file_name="variation_summary.csv", mime="text/csv")

    st.success("Selesai — pastikan nama kolom di sheet sesuai atau gunakan preview untuk menyesuaikan.")