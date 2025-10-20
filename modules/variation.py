import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dbConfig import get_db_connection
from dataManager import load_all_data
from google import genai

# bobot berdasarkan kata kunci (case-insensitive)
BOBOT_MAP = {
    "coach": 1.5,
    "mentor": 1.4,
    "speaker": 1.3,
    "teach": 1.2,
    "content": 1.1,
    "publikasi": 1.0,
    "publication": 1.0,
    "article": 1.0
}

def _find_col(df, candidates):
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    for col in df.columns:
        low = col.lower()
        for cand in candidates:
            if cand.lower() in low:
                return col
    return None

def _norm_text(s):
    if pd.isna(s):
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def _assign_bobot_from_text(text):
    s = _norm_text(text)
    for k, v in BOBOT_MAP.items():
        if k in s:
            return v
    return 1.0

def _load_nameact_mapping(mfile):
    try:
        if isinstance(mfile, (str, os.PathLike)) and os.path.exists(mfile):
            mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
        else:
            mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
    except Exception:
        return None
    mp = mp.rename(columns={c: c.strip() for c in mp.columns})
    name_col = _find_col(mp, ["name"])
    act_col = _find_col(mp, ["activity", "course_name", "course"])
    if not name_col or not act_col:
        return None
    pairs = mp[[name_col, act_col]].dropna(how="all").copy()
    pairs.columns = ["NAME", "ACTIVITY"]
    pairs["NAME_UP"] = pairs["NAME"].astype(str).str.strip().str.upper()
    pairs["ACTIVITY_NORM"] = pairs["ACTIVITY"].apply(_norm_text)
    pairs = pairs.drop_duplicates(subset=["NAME_UP", "ACTIVITY_NORM"])
    return pairs[["NAME_UP", "ACTIVITY_NORM", "ACTIVITY"]]

def variation_page():
    st.title("Parameter 3 — Poin Variasi Penugasan (Variation)")

    st.markdown("Unggah file `Agustus 2025.xlsx` (sheet 'General') dan file mapping `nameactlim1` (kolom Name, Activity). Pilih sumber data seperti pada modul Learning Hour.")

    source = st.pills("Data Resource", ["Upload file", "From Data Base"], selection_mode="single", default="Upload file")
    col1, col2 = st.columns([1,1])
    with col1:
        uploaded = st.file_uploader("Upload data Excel (Agustus 2025.xlsx)", type=["xlsx","xls"], key="var_main")
    with col2:
        mapfile = st.file_uploader("Upload nameactlim1 (mapping LIM1)", type=["xlsx","xls"], key="var_map")

    # fallback ke file lokal jika user tidak upload
    if uploaded is None and os.path.exists("Agustus 2025.xlsx"):
        uploaded = "Agustus 2025.xlsx"
    if mapfile is None and os.path.exists("nameactlim1.xlsx"):
        mapfile = "nameactlim1.xlsx"

    df_main = pd.DataFrame()
    if source == "From Data Base":
        viewTable = "General"  # sesuaikan jika view berbeda
        try:
            df_main = load_all_data(viewTable)
        except Exception as e:
            st.error(f"Gagal ambil data dari DB: {e}")
            return
    else:
        if uploaded is None:
            st.info("Silakan unggah file data utama (Agustus 2025.xlsx) atau pilih From Data Base.")
            return
        try:
            if isinstance(uploaded, (str, os.PathLike)):
                df_main = pd.read_excel(uploaded, sheet_name="General", dtype=str)
            else:
                df_main = pd.read_excel(uploaded, sheet_name="General", dtype=str)
        except Exception as e:
            st.error(f"Gagal membaca sheet 'General': {e}")
            return

    if mapfile is None:
        st.info("Silakan unggah file nameactlim1 (mapping LIM1) atau taruh nameactlim1.xlsx di folder project.")
        return

    mapping_df = _load_nameact_mapping(mapfile)
    if mapping_df is None or mapping_df.empty:
        st.error("Gagal membaca mapping nameactlim1. Pastikan ada kolom 'Name' dan 'Activity'.")
        return

    # deteksi kolom penting di sheet General
    col_nik = _find_col(df_main, ["nik", "id"])
    col_name = _find_col(df_main, ["name", "nama"])
    col_sub = _find_col(df_main, ["sub_penugasan", "sub penugasan"])
    col_activities = _find_col(df_main, ["activities", "activity"])
    col_course = _find_col(df_main, ["course_name", "course", "course name"])
    col_bobot = _find_col(df_main, ["bobot lh", "bobot_lh", "bobot"])

    if not col_name:
        st.error("Kolom 'name' tidak ditemukan di sheet 'General'.")
        return

    df_main = df_main.rename(columns={c: c.strip() for c in df_main.columns})
    df_main["NAME_UP"] = df_main[col_name].astype(str).str.strip().str.upper()
    df_main["COURSE_NORM"] = df_main[col_course].apply(_norm_text) if col_course else ""
    df_main["ACTIVITIES_NORM"] = df_main[col_activities].apply(_norm_text) if col_activities else ""
    df_main["SUB_PENUGASAN"] = df_main[col_sub].astype(str).fillna("") if col_sub else ""
    df_main["NIK"] = df_main[col_nik].astype(str).fillna("") if col_nik else ""

    # filter hanya nama yang ada di mapping
    lim1_names = set(mapping_df["NAME_UP"].tolist())
    df_lim1 = df_main[df_main["NAME_UP"].isin(lim1_names)].copy()
    if df_lim1.empty:
        st.warning("Tidak ada baris di sheet 'General' yang cocok dengan mapping nameactlim1.")
        return

    st.subheader("Preview data (baris yang cocok dengan LIM1)")
    preview_cols = []
    if col_nik: preview_cols.append(col_nik)
    preview_cols += [col_name]
    if col_sub: preview_cols.append(col_sub)
    if col_activities: preview_cols.append(col_activities)
    if col_course: preview_cols.append(col_course)
    st.dataframe(df_lim1[preview_cols].head(200))

    # hitung frekuensi berdasarkan pasangan name+course_name pada mapping
    records = []
    for _, pair in mapping_df.iterrows():
        name_up = pair["NAME_UP"]
        act_norm = pair["ACTIVITY_NORM"]
        act_display = pair.get("ACTIVITY", "")
        df_person = df_lim1[df_lim1["NAME_UP"] == name_up]
        if df_person.empty:
            continue
        mask = df_person["COURSE_NORM"].str.contains(act_norm, na=False) | df_person["ACTIVITIES_NORM"].str.contains(act_norm, na=False)
        freq = int(mask.sum())
        if freq == 0:
            continue
        sample = df_person[mask].iloc[0]
        nik_val = sample.get("NIK", "")
        name_val = sample.get(col_name, sample.get("NAME_UP", ""))
        sub_pen = sample.get("SUB_PENUGASAN", "")
        explicit_bobot = None
        if col_bobot:
            try:
                explicit_bobot = float(str(sample.get(col_bobot)).replace(",", "."))
            except Exception:
                explicit_bobot = None
        bobot_lh = explicit_bobot if explicit_bobot and explicit_bobot > 0 else _assign_bobot_from_text(sub_pen) or _assign_bobot_from_text(act_display)
        point = round(bobot_lh * freq, 2)
        records.append({
            "NIK": nik_val,
            "NAME": name_val,
            "SUB_PENUGASAN": sub_pen,
            "ACTIVITIES": act_display,
            "course_name": act_display,
            "BOBOT LH": bobot_lh,
            "FREKUENSI": freq,
            "POIN BOBOT": point
        })

    if not records:
        st.info("Tidak ditemukan pasangan name+course_name pada data utama sesuai mapping.")
        return

    df_records = pd.DataFrame.from_records(records)
    df_records.insert(0, "no", range(1, len(df_records) + 1))

    # tampilkan tabel dengan styling header oranye (menggunakan to_html)
    styler = (df_records[["no","NIK","NAME","SUB_PENUGASAN","ACTIVITIES","course_name","BOBOT LH","FREKUENSI","POIN BOBOT"]]
              .style.set_table_styles([{"selector":"th","props":[("background-color","#d9643a"),("color","white")]},
                                       {"selector":"td","props":[("padding","6px")]}])
              .format({"BOBOT LH": "{:.2f}", "POIN BOBOT": "{:.2f}"}))
    st.subheader("Detail per record")
    st.markdown(styler.to_html(), unsafe_allow_html=True)

    # ringkasan per expert
    summary = (df_records
               .groupby(["NIK","NAME"], as_index=False)
               .agg(total_point=("POIN BOBOT","sum"),
                    total_freq=("FREKUENSI","sum"))
               .sort_values("total_point", ascending=False))
    st.subheader("Ringkasan per Expert (Total Point)")
    st.dataframe(summary)

    max_point = st.number_input("Total Point Tertinggi (untuk normalisasi skor)", value=25.0, step=1.0)
    min_total_point = st.number_input("Minimal Total Point Expert (batas bawah)", value=1.0, step=0.1)

    summary["total_point_clamped"] = summary["total_point"].apply(lambda v: max(v, float(min_total_point)))
    summary["score_percent"] = (summary["total_point_clamped"] / float(max_point)) * 100
    summary["score_percent"] = summary["score_percent"].clip(0,100).round(2)

    st.subheader("Skor Normalisasi (Top 20)")
    st.dataframe(summary.head(20))

    # download
    csv_bytes = df_records.to_csv(index=False).encode("utf-8")
    st.download_button("Download detail CSV", data=csv_bytes, file_name="variation_detail.csv", mime="text/csv")
    st.download_button("Download summary CSV", data=summary.to_csv(index=False).encode("utf-8"), file_name="variation_summary.csv", mime="text/csv")

    # Analisis singkat via OpenAI (genai) - optional, non-blocking
    try:
        top3 = summary.head(3).to_dict(orient="records")
        prompt = "Buat ringkasan singkat (3 kalimat) tentang top 3 expert berdasarkan total_point: " + str(top3)
        resp = genai.responses.create(model="models/text-bison-001", input=prompt)
        analysis = resp.output[0].content[0].text if hasattr(resp, "output") else str(resp)
        st.subheader("Analisis (OpenAI)")
        st.write(analysis)
    except Exception:
        # jangan ganggu flow jika gagal panggil genai
        st.info("Analisis OpenAI tidak tersedia (cek konfigurasi genai).")
 
# filepath: e:\CorpU\EXMAN\expert-calculator\modules\variation.py
import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dbConfig import get_db_connection
from dataManager import load_all_data
from google import genai

# bobot berdasarkan kata kunci (case-insensitive)
BOBOT_MAP = {
    "coach": 1.5,
    "mentor": 1.4,
    "speaker": 1.3,
    "teach": 1.2,
    "content": 1.1,
    "publikasi": 1.0,
    "publication": 1.0,
    "article": 1.0
}

def _find_col(df, candidates):
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    for col in df.columns:
        low = col.lower()
        for cand in candidates:
            if cand.lower() in low:
                return col
    return None

def _norm_text(s):
    if pd.isna(s):
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def _assign_bobot_from_text(text):
    s = _norm_text(text)
    for k, v in BOBOT_MAP.items():
        if k in s:
            return v
    return 1.0

def _load_nameact_mapping(mfile):
    try:
        if isinstance(mfile, (str, os.PathLike)) and os.path.exists(mfile):
            mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
        else:
            mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
    except Exception:
        return None
    mp = mp.rename(columns={c: c.strip() for c in mp.columns})
    name_col = _find_col(mp, ["name"])
    act_col = _find_col(mp, ["activity", "course_name", "course"])
    if not name_col or not act_col:
        return None
    pairs = mp[[name_col, act_col]].dropna(how="all").copy()
    pairs.columns = ["NAME", "ACTIVITY"]
    pairs["NAME_UP"] = pairs["NAME"].astype(str).str.strip().str.upper()
    pairs["ACTIVITY_NORM"] = pairs["ACTIVITY"].apply(_norm_text)
    pairs = pairs.drop_duplicates(subset=["NAME_UP", "ACTIVITY_NORM"])
    return pairs[["NAME_UP", "ACTIVITY_NORM", "ACTIVITY"]]

def variation_page():
    st.title("Parameter 3 — Poin Variasi Penugasan (Variation)")

    st.markdown("Unggah file `Agustus 2025.xlsx` (sheet 'General') dan file mapping `nameactlim1` (kolom Name, Activity). Pilih sumber data seperti pada modul Learning Hour.")

    source = st.pills("Data Resource", ["Upload file", "From Data Base"], selection_mode="single", default="Upload file")
    col1, col2 = st.columns([1,1])
    with col1:
        uploaded = st.file_uploader("Upload data Excel (Agustus 2025.xlsx)", type=["xlsx","xls"], key="var_main")
    with col2:
        mapfile = st.file_uploader("Upload nameactlim1 (mapping LIM1)", type=["xlsx","xls"], key="var_map")

    # fallback ke file lokal jika user tidak upload
    if uploaded is None and os.path.exists("Agustus 2025.xlsx"):
        uploaded = "Agustus 2025.xlsx"
    if mapfile is None and os.path.exists("nameactlim1.xlsx"):
        mapfile = "nameactlim1.xlsx"

    df_main = pd.DataFrame()
    if source == "From Data Base":
        viewTable = "General"  # sesuaikan jika view berbeda
        try:
            df_main = load_all_data(viewTable)
        except Exception as e:
            st.error(f"Gagal ambil data dari DB: {e}")
            return
    else:
        if uploaded is None:
            st.info("Silakan unggah file data utama (Agustus 2025.xlsx) atau pilih From Data Base.")
            return
        try:
            if isinstance(uploaded, (str, os.PathLike)):
                df_main = pd.read_excel(uploaded, sheet_name="General", dtype=str)
            else:
                df_main = pd.read_excel(uploaded, sheet_name="General", dtype=str)
        except Exception as e:
            st.error(f"Gagal membaca sheet 'General': {e}")
            return

    if mapfile is None:
        st.info("Silakan unggah file nameactlim1 (mapping LIM1) atau taruh nameactlim1.xlsx di folder project.")
        return

    mapping_df = _load_nameact_mapping(mapfile)
    if mapping_df is None or mapping_df.empty:
        st.error("Gagal membaca mapping nameactlim1. Pastikan ada kolom 'Name' dan 'Activity'.")
        return

    # deteksi kolom penting di sheet General
    col_nik = _find_col(df_main, ["nik", "id"])
    col_name = _find_col(df_main, ["name", "nama"])
    col_sub = _find_col(df_main, ["sub_penugasan", "sub penugasan"])
    col_activities = _find_col(df_main, ["activities", "activity"])
    col_course = _find_col(df_main, ["course_name", "course", "course name"])
    col_bobot = _find_col(df_main, ["bobot lh", "bobot_lh", "bobot"])

    if not col_name:
        st.error("Kolom 'name' tidak ditemukan di sheet 'General'.")
        return

    df_main = df_main.rename(columns={c: c.strip() for c in df_main.columns})
    df_main["NAME_UP"] = df_main[col_name].astype(str).str.strip().str.upper()
    df_main["COURSE_NORM"] = df_main[col_course].apply(_norm_text) if col_course else ""
    df_main["ACTIVITIES_NORM"] = df_main[col_activities].apply(_norm_text) if col_activities else ""
    df_main["SUB_PENUGASAN"] = df_main[col_sub].astype(str).fillna("") if col_sub else ""
    df_main["NIK"] = df_main[col_nik].astype(str).fillna("") if col_nik else ""

    # filter hanya nama yang ada di mapping
    lim1_names = set(mapping_df["NAME_UP"].tolist())
    df_lim1 = df_main[df_main["NAME_UP"].isin(lim1_names)].copy()
    if df_lim1.empty:
        st.warning("Tidak ada baris di sheet 'General' yang cocok dengan mapping nameactlim1.")
        return

    st.subheader("Preview data (baris yang cocok dengan LIM1)")
    preview_cols = []
    if col_nik: preview_cols.append(col_nik)
    preview_cols += [col_name]
    if col_sub: preview_cols.append(col_sub)
    if col_activities: preview_cols.append(col_activities)
    if col_course: preview_cols.append(col_course)
    st.dataframe(df_lim1[preview_cols].head(200))

    # hitung frekuensi berdasarkan pasangan name+course_name pada mapping
    records = []
    for _, pair in mapping_df.iterrows():
        name_up = pair["NAME_UP"]
        act_norm = pair["ACTIVITY_NORM"]
        act_display = pair.get("ACTIVITY", "")
        df_person = df_lim1[df_lim1["NAME_UP"] == name_up]
        if df_person.empty:
            continue
        mask = df_person["COURSE_NORM"].str.contains(act_norm, na=False) | df_person["ACTIVITIES_NORM"].str.contains(act_norm, na=False)
        freq = int(mask.sum())
        if freq == 0:
            continue
        sample = df_person[mask].iloc[0]
        nik_val = sample.get("NIK", "")
        name_val = sample.get(col_name, sample.get("NAME_UP", ""))
        sub_pen = sample.get("SUB_PENUGASAN", "")
        explicit_bobot = None
        if col_bobot:
            try:
                explicit_bobot = float(str(sample.get(col_bobot)).replace(",", "."))
            except Exception:
                explicit_bobot = None
        bobot_lh = explicit_bobot if explicit_bobot and explicit_bobot > 0 else _assign_bobot_from_text(sub_pen) or _assign_bobot_from_text(act_display)
        point = round(bobot_lh * freq, 2)
        records.append({
            "NIK": nik_val,
            "NAME": name_val,
            "SUB_PENUGASAN": sub_pen,
            "ACTIVITIES": act_display,
            "course_name": act_display,
            "BOBOT LH": bobot_lh,
            "FREKUENSI": freq,
            "POIN BOBOT": point
        })

    if not records:
        st.info("Tidak ditemukan pasangan name+course_name pada data utama sesuai mapping.")
        return

    df_records = pd.DataFrame.from_records(records)
    df_records.insert(0, "no", range(1, len(df_records) + 1))

    # tampilkan tabel dengan styling header oranye (menggunakan to_html)
    styler = (df_records[["no","NIK","NAME","SUB_PENUGASAN","ACTIVITIES","course_name","BOBOT LH","FREKUENSI","POIN BOBOT"]]
              .style.set_table_styles([{"selector":"th","props":[("background-color","#d9643a"),("color","white")]},
                                       {"selector":"td","props":[("padding","6px")]}])
              .format({"BOBOT LH": "{:.2f}", "POIN BOBOT": "{:.2f}"}))
    st.subheader("Detail per record")
    st.markdown(styler.to_html(), unsafe_allow_html=True)

    # ringkasan per expert
    summary = (df_records
               .groupby(["NIK","NAME"], as_index=False)
               .agg(total_point=("POIN BOBOT","sum"),
                    total_freq=("FREKUENSI","sum"))
               .sort_values("total_point", ascending=False))
    st.subheader("Ringkasan per Expert (Total Point)")
    st.dataframe(summary)

    max_point = st.number_input("Total Point Tertinggi (untuk normalisasi skor)", value=25.0, step=1.0)
    min_total_point = st.number_input("Minimal Total Point Expert (batas bawah)", value=1.0, step=0.1)

    summary["total_point_clamped"] = summary["total_point"].apply(lambda v: max(v, float(min_total_point)))
    summary["score_percent"] = (summary["total_point_clamped"] / float(max_point)) * 100
    summary["score_percent"] = summary["score_percent"].clip(0,100).round(2)

    st.subheader("Skor Normalisasi (Top 20)")
    st.dataframe(summary.head(20))

    # download
    csv_bytes = df_records.to_csv(index=False).encode("utf-8")
    st.download_button("Download detail CSV", data=csv_bytes, file_name="variation_detail.csv", mime="text/csv")
    st.download_button("Download summary CSV", data=summary.to_csv(index=False).encode("utf-8"), file_name="variation_summary.csv", mime="text/csv")

    # Analisis singkat via OpenAI (genai) - optional, non-blocking
    try:
        top3 = summary.head(3).to_dict(orient="records")
        prompt = "Buat ringkasan singkat (3 kalimat) tentang top 3 expert berdasarkan total_point: " + str(top3)
        resp = genai.responses.create(model="models/text-bison-001", input=prompt)
        analysis = resp.output[0].content[0].text if hasattr(resp, "output") else str(resp)
        st.subheader("Analisis (OpenAI)")
        st.write(analysis)
    except Exception:
        # jangan ganggu flow jika gagal panggil genai
        st.info("Analisis OpenAI tidak tersedia (cek konfigurasi genai).")