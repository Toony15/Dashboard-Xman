import os
import re
import unicodedata

import pandas as pd
import streamlit as st

from dataManager import load_all_data
from google import genai

# bobot berdasarkan kata kunci (case-insensitive) - fallback jika tidak ada nilai eksplisit
BOBOT_MAP = {
    "coach": 1.5,
    "mentor": 1.4,
    "speaker": 1.3,
    "teach": 1.2,
    "content": 1.1,
    "publikasi": 1.0,
    "publication": 1.0,
    "article": 1.0,
    "self learning": 1.0
}


def _find_col(df: pd.DataFrame, candidates):
    """
    Find first column name in df that matches any candidate (exact or substring, case-insensitive).
    Returns actual column name or None.
    """
    cols = {str(c).lower().strip(): c for c in df.columns}
    for cand in candidates:
        if not cand:
            continue
        k = cand.lower().strip()
        if k in cols:
            return cols[k]
    # fallback: substring match
    for col in df.columns:
        low = str(col).lower()
        for cand in candidates:
            if not cand:
                continue
            if cand.lower().strip() in low:
                return col
    return None


def _norm_text(s):
    if pd.isna(s) or s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _assign_bobot_from_text(text):
    """
    If text is numeric (e.g. '1.4' or '1,4') return float.
    Else match keywords in BOBOT_MAP.
    Default 1.0.
    """
    if text is None:
        return 1.0
    t = str(text).strip()
    if t == "":
        return 1.0
    # numeric first
    try:
        return float(t.replace(",", "."))
    except Exception:
        pass
    s = _norm_text(t)
    for k, v in BOBOT_MAP.items():
        if k in s:
            return v
    return 1.0


def variation_page():
    """
    Streamlit page: two modes:
      - Upload file: user uploads single Excel (sheet 'General')
      - From Data Base: app fetches data from DB (learningImpact1)
    
    ✅ FIXED: HAPUS FILTER MAPPING - PROSES SEMUA DATA (258 rows)
    """
    st.title("Parameter 3 — Poin Variasi Penugasan")
    st.markdown("pilih menu Upload/Database")

    source = st.radio("Data Resource", ["Upload file", "From Data Base"], index=0)

    uploaded = None

    if source == "Upload file":
        uploaded = st.file_uploader("Upload file (sheet 'General') — hanya 1 file", type=["xlsx", "xls"], key="var_main")
        st.info("Mode Upload: unggah satu file Excel yang memuat sheet 'General'.")
    else:
        st.info("Mode DB: data utama diambil dari database (view/table 'learningImpact1').")

    # local fallback for convenience
    if source == "Upload file" and uploaded is None and os.path.exists("Agustus 2025.xlsx"):
        uploaded = "Agustus 2025.xlsx"

    # load main data
    try:
        if source == "From Data Base":
            df_main = load_all_data("learningImpact1")
        else:
            if uploaded is None:
                st.info("Silakan unggah file atau pilih 'From Data Base'.")
                return
            df_main = pd.read_excel(uploaded, sheet_name="General", dtype=str)
    except Exception as e:
        st.error(f"Gagal ambil/membaca data utama: {e}")
        return
    
    st.info(f"📊 Total baris data: {len(df_main)}")
    
    # --- Quarter filter UI and date column auto-detection ---
    quarter_choice = st.selectbox("Filter Quarter", ["All", "Q1", "Q2", "Q3", "Q4"], index=0)

    date_col_candidates = ["date", "tanggal", "event_date", "start_date", "activity_date", "date_event"]
    date_col = _find_col(df_main, date_col_candidates)

    if date_col is None:
        st.info("Kolom tanggal tidak ditemukan otomatis — menampilkan semua data.")
    else:
        try:
            df_main["__PARSED_DATE__"] = pd.to_datetime(df_main[date_col], errors="coerce")
            df_main["__QUARTER__"] = df_main["__PARSED_DATE__"].dt.quarter

            if quarter_choice != "All":
                qnum = int(quarter_choice.replace("Q", ""))
                df_main = df_main[df_main["__QUARTER__"] == qnum].copy()
                st.info(f"Menampilkan data untuk {quarter_choice} (berdasarkan kolom '{date_col}'). Total: {len(df_main)} baris")
        except Exception:
            st.info("Gagal memproses kolom tanggal untuk filter quarter; menampilkan semua data.")
    # --- Selesai filter quarter ---

    # ============================================
    # ✅ FIXED: HAPUS FILTER MAPPING
    # Detect columns dan process SEMUA data tanpa filter
    # ============================================
    
    col_nik = _find_col(df_main, ["nik", "id"])
    col_name = _find_col(df_main, ["name", "expert", "nama"])
    col_course = _find_col(df_main, ["course_name", "course", "event", "course name"])
    col_variasi = _find_col(df_main, ["variasi", "variation"])
    col_sub = _find_col(df_main, ["sub_penugasan", "penugasan"])

    if not col_name or not col_course:
        st.error("Kolom 'name' atau 'course_name/event' tidak ditemukan di data utama.")
        return

    # normalize
    df_main = df_main.rename(columns={c: c.strip() for c in df_main.columns})
    df_main["NAME_UP"] = df_main[col_name].astype(str).str.strip().str.upper()
    df_main["EVENT_NORM"] = df_main[col_course].apply(_norm_text)
    df_main["VARIASI_TEXT"] = df_main[col_variasi].astype(str).fillna("") if col_variasi else ""
    df_main["SUB_PENUGASAN"] = df_main[col_sub].astype(str).fillna("") if col_sub else ""

    # ✅ TIDAK ADA FILTER - GUNAKAN SEMUA DATA
    df_filtered = df_main.copy()
    
    if df_filtered.empty:
        st.warning("Tidak ada data untuk diproses.")
        return

    st.info(f"✅ Memproses {len(df_filtered)} data (tanpa filter mapping)")

    # --- Preview with quarter filter ---
    quarter_col = _find_col(df_filtered, ["quarter", "__QUARTER__", "Quarter"])

    if quarter_col is not None:
        available = list(dict.fromkeys(df_filtered[quarter_col].dropna().astype(str).tolist()))
        order = ["Q1", "Q2", "Q3", "Q4"]
        available_sorted = [q for q in order if q in available] + [q for q in available if q not in order]
        preview_choices = ["All"] + available_sorted
    else:
        preview_choices = ["All"]

    preview_q = st.selectbox("Filter Preview by Quarter", preview_choices, index=0, key="preview_quarter")

    if preview_q == "All" or quarter_col is None:
        df_filtered_preview = df_filtered.copy()
    else:
        df_filtered_preview = df_filtered[df_filtered[quarter_col].astype(str) == preview_q].copy()

    st.subheader(f"Preview ({len(df_filtered_preview)} baris)")
    preview_cols = [col_name, col_course]
    if col_sub:
        preview_cols.append(col_sub)
    if col_variasi:
        preview_cols.append(col_variasi)
    st.dataframe(df_filtered_preview[preview_cols].head(200))

    # ============================================
    # Aggregate by expert + event (count frequency) and compute bobot from 'variasi'
    # ============================================
    rows = []
    grouped = df_filtered.groupby(["NAME_UP", "EVENT_NORM"], dropna=False)
    for (name_up, ev_norm), group in grouped:
        freq = int(len(group))
        sample = group.iloc[0]
        name_val = sample.get(col_name, name_up)
        activity_display = sample.get(col_course, "")
        sub_pen = sample.get("SUB_PENUGASAN", "")

        # prefer variasi column values (first non-empty)
        variasi_vals = [str(x).strip() for x in group["VARIASI_TEXT"].tolist() if str(x).strip()]
        bobot = None
        if variasi_vals:
            # try numeric first
            for v in variasi_vals:
                try:
                    bobot = float(v.replace(",", "."))
                    break
                except Exception:
                    pass
            if bobot is None:
                bobot = _assign_bobot_from_text(variasi_vals[0])
        else:
            # fallback to sub_pen or activity_display inference
            bobot = _assign_bobot_from_text(sub_pen or activity_display or "")

        point = round(bobot * freq, 2)
        rows.append({
            "NAME": name_val,
            "EVENT": activity_display,
            "EVENT_NORM": ev_norm,
            "BOBOT LH": bobot,
            "FREKUENSI": freq,
            "POIN BOBOT": point
        })

    df_records = pd.DataFrame(rows)
    if df_records.empty:
        st.info("Tidak ditemukan record setelah agregasi.")
        return
    df_records.insert(0, "no", range(1, len(df_records) + 1))

    st.subheader(f"Detail Variasi Penugasan (filtered) — {len(df_records)} expert")
    # remove orange header styling; keep minimal padding and number formatting
    styler = (df_records[["no", "NAME", "EVENT", "BOBOT LH", "FREKUENSI", "POIN BOBOT"]]
              .style.set_table_styles([
                  {"selector": "th", "props": [("padding", "6px"), ("text-align", "left")]},
                  {"selector": "td", "props": [("padding", "6px")]}
              ]).format({"BOBOT LH": "{:.2f}", "POIN BOBOT": "{:.2f}"}))
    st.markdown(styler.to_html(), unsafe_allow_html=True)

    # summary per expert (group by NAME only)
    summary = (df_records
               .groupby(["NAME"], as_index=False)
               .agg(total_point=("POIN BOBOT", "sum"))
               .sort_values("total_point", ascending=False))
    
    st.subheader(f"Ringkasan per Expert (Total Point) — {len(summary)} expert")
    st.dataframe(summary)

    # downloads (CSV won't include NIK)
    st.download_button("Download detail CSV", data=df_records.to_csv(index=False).encode("utf-8"), file_name="variation_detail.csv", mime="text/csv")
    st.download_button("Download summary CSV", data=summary.to_csv(index=False).encode("utf-8"), file_name="variation_summary.csv", mime="text/csv")


if __name__ == "__main__":
    variation_page()