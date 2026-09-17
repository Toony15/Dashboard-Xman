import io
import locale

import pandas as pd
import streamlit as st

from dataManager import load_all_data
from dbConfig import get_db_connection

try:
    locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, '')


TABEL_SUMBER = "calculated"
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
EXCLUDE_NIK = [860066, 910156, 730329]  # NIK EXMAN
SKOR_COLS = ["learning_hour", "variation", "final_expert_level", "impact_expert"]
REQUIRED_COLS = ["nik", "expert"] + SKOR_COLS


def fmt_rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")


def parse_budget(raw_text):
    """Ubah input teks budget (boleh pakai titik ribuan) jadi float, atau None kalau kosong/invalid."""
    if not raw_text.strip():
        return None
    digits = "".join(ch for ch in raw_text if ch.isdigit())
    if not digits:
        st.error("Format nominal tidak valid. Contoh yang benar: 100.000.000")
        return None
    budget = float(digits)
    st.caption(f"Nominal terbaca: {fmt_rupiah(budget)}")
    return budget


def load_all_scores():
    """Ambil seluruh data dari tabel 'calculated' (semua quarter)."""
    return load_all_data(TABEL_SUMBER)


def filter_data(df, min_lh, exclude_exman, terapkan_min_lh):
    """
    Terapkan filter Minimal Learning Hour (hanya jika `terapkan_min_lh` True -
    lihat pemanggilnya untuk alasan kenapa ini digerbang oleh budget) dan
    Exclude EXMAN (langsung aktif begitu toggle-nya dinyalakan).
    """
    if terapkan_min_lh and "learning_hour" in df.columns:
        df = df[df["learning_hour"] >= min_lh].copy()
    if exclude_exman:
        df = df[~df["nik"].isin(EXCLUDE_NIK)].copy()
    return df


def score(df):
    """Isi kekosongan kolom skor dengan 0, lalu hitung skor_akhir (penjumlahan langsung)."""
    df = df.copy()
    for col in SKOR_COLS:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)
    df["skor_akhir"] = df[SKOR_COLS].sum(axis=1)
    return df


def compensate(df, budget):
    """Bagi budget proporsional terhadap skor_akhir tiap expert."""
    df = df.copy()
    total_skor = df["skor_akhir"].sum()
    if budget and budget > 0 and total_skor > 0:
        df["kompensasi"] = (df["skor_akhir"] / total_skor) * budget
    else:
        df["kompensasi"] = 0
        if budget and budget > 0:
            st.warning("⚠️ Total skor adalah 0, tidak bisa menghitung kompensasi")
    return df


def show_summary(df, budget):
    cols = st.columns(4)
    cols[0].metric("Total Expert", len(df), border=True)
    cols[1].metric("Total Skor Akhir", f"{df['skor_akhir'].sum():.2f}", border=True)
    cols[2].metric("Total Budget", fmt_rupiah(budget) if budget else "Rp 0", border=True)

    avg_comp = df["kompensasi"].sum() / len(df) if budget and len(df) > 0 else 0
    cols[3].metric("Rata-rata Kompensasi", fmt_rupiah(avg_comp), border=True)


def show_detail(df):
    st.subheader("Detail Perhitungan Kompensasi per Expert")
    display_df = df.copy()
    display_df["kompensasi (Rp)"] = display_df["kompensasi"].apply(fmt_rupiah)
    cols = ["nik", "expert", *SKOR_COLS, "skor_akhir", "kompensasi (Rp)"]
    st.dataframe(display_df[cols], use_container_width=True)


def show_stats(df, budget):
    st.subheader("Statistik Kompensasi")
    cols = st.columns(3)
    cols[0].metric("Kompensasi Tertinggi", fmt_rupiah(df["kompensasi"].max()) if budget else "Rp 0", border=True)
    cols[1].metric("Kompensasi Terendah", fmt_rupiah(df["kompensasi"].min()) if budget else "Rp 0", border=True)
    if budget and len(df) > 0:
        cols[2].metric("Std Deviation Kompensasi", fmt_rupiah(df["kompensasi"].std()), border=True)


def export_excel(df, quarter):
    if not st.button("Download Hasil Kompensasi (Excel)", key="btn_download_comp"):
        return

    cols = ["nik", "expert", "quarter", *SKOR_COLS, "skor_akhir", "kompensasi"]
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df[cols].to_excel(writer, sheet_name="Kompensasi", index=False)
    buffer.seek(0)

    st.download_button(
        label="Download Kompensasi.xlsx",
        data=buffer,
        file_name=f"Kompensasi_{quarter}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def compensation():
    """
    Menghitung Compensation berdasarkan skema 2026.

    Nilai learning_hour, variation, final_expert_level, dan impact_expert di
    tabel 'calculated' SUDAH merupakan hasil akhir perhitungan bobot % dari
    fitur lain (Learning Hour, Variation, Expert Level, Expert Impact), jadi
    di sini keempatnya cukup DIJUMLAHKAN LANGSUNG.

    Formula:
    1. skor_akhir = learning_hour + variation + final_expert_level + impact_expert
    2. kompensasi = (skor_akhir / total_skor_akhir) * budget

    Catatan filter: tabel & metrik menampilkan SEMUA expert quarter terpilih
    sampai nominal kompensasi (budget) diisi. Filter Minimal Learning Hour
    baru diterapkan setelah budget diisi, supaya user bisa lihat data lengkap
    dulu sebelum memutuskan kriteria filter.
    """
    get_db_connection()  # pastikan koneksi DB siap sebelum load_all_data dipanggil

    st.title("💰 Compensation Calculator")
    st.pills("Data Resource", ["From Data Base"], selection_mode="single", default="From Data Base")

    raw_df = load_all_scores()
    if raw_df.empty:
        st.info(
            "Tidak terdapat data di tabel 'calculated'. Pastikan sudah menjalankan "
            "perhitungan Learning Hour, Variation, Expert Level, dan Expert Impact terlebih dahulu."
        )
        return None

    quarter = st.pills("Pilih Quarter", QUARTERS, selection_mode="single", default="Q1")
    df = raw_df[raw_df["quarter"] == quarter].copy()

    st.dataframe(df)

    if df.empty:
        st.warning(f"Tidak ada data untuk quarter {quarter}.")
        return None

    comp_cols = st.columns(2)
    with comp_cols[0]:
        st.header("Nominal Kompensasi")
        budget_raw = st.text_input(
            "Nominal Kompensasi Total (Rp)", value="",
            placeholder="Contoh: 100.000.000 atau 100000000", key="input_budget_text",
            help="Boleh diketik pakai titik pemisah ribuan (100.000.000) maupun angka polos (100000000).",
        )
        budget = parse_budget(budget_raw)

    with comp_cols[1]:
        st.header("Filter Learning Hour Minimal")
        min_lh = st.number_input(
            "Minimal Learning Hour per Quarter", value=10, min_value=0, key="input_min_lh",
            help=(
                "Sesuai kriteria skema 2026: minimal Learning Hour 10 jam. Filter ini baru "
                "diterapkan setelah nominal kompensasi di atas diisi - sebelum itu, tabel di "
                "bawah menampilkan SEMUA expert quarter ini."
            ),
        )

    terapkan_min_lh = bool(budget and budget > 0)
    if not terapkan_min_lh:
        st.caption(f"ℹ️ Filter Minimal Learning Hour ({min_lh}) belum diterapkan - isi nominal kompensasi di atas untuk menerapkannya.")

    exclude_exman = st.toggle("Exclude EXMAN (Exclude NIK tertentu)", value=False)
    if exclude_exman:
        st.info("EXMAN telah dikecualikan dari perhitungan")

    df = filter_data(df, min_lh, exclude_exman, terapkan_min_lh)

    missing_cols = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing_cols:
        st.error(f"Kolom yang hilang: {missing_cols}")
        st.info(f"Data saat ini memiliki kolom: {df.columns.tolist()}")
        return None

    if df.empty:
        st.warning("Tidak ada expert yang memenuhi filter Learning Hour minimal / exclude EXMAN.")
        return None

    df = score(df)
    df = compensate(df, budget)
    if not (budget and budget > 0):
        st.info("Masukkan nominal kompensasi untuk melihat distribusi kompensasi")

    st.header("Hasil Perhitungan Compensation")
    show_summary(df, budget)
    show_detail(df)
    show_stats(df, budget)
    export_excel(df, quarter)

    return df

if __name__ == "__main__":
    compensation()