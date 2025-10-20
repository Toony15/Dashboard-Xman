# ...existing code...
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
    "article": 1.0
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


def _load_nameact_mapping(mfile):
    """
    Load mapping list (Name | Activity).
    If mfile provided, read first sheet and detect name/activity columns.
    Otherwise use built-in list provided by user.
    Returns DataFrame with columns: NAME_UP, ACTIVITY_NORM, ACTIVITY
    """
    if mfile is not None:
        try:
            if isinstance(mfile, (str, os.PathLike)) and os.path.exists(mfile):
                mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
            else:
                mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
            mp = mp.rename(columns={c: c.strip() for c in mp.columns})
            name_col = _find_col(mp, ["name", "nama", "expert"])
            act_col = _find_col(mp, ["activity", "course_name", "course", "event"])
            if name_col is None and act_col is None:
                return None
            cols = []
            if name_col is not None:
                cols.append(name_col)
            if act_col is not None:
                cols.append(act_col)
            pairs = mp[cols].copy()
            rename_map = {}
            if name_col is not None:
                rename_map[name_col] = "NAME"
            if act_col is not None:
                rename_map[act_col] = "ACTIVITY"
            pairs = pairs.rename(columns=rename_map)
            if "NAME" not in pairs.columns:
                pairs["NAME"] = ""
            if "ACTIVITY" not in pairs.columns:
                pairs["ACTIVITY"] = ""
        except Exception:
            return None
    else:
        # built-in mapping (user-provided list). Keep trimmed.
        mapping_text = """ABDUL HAMID ARROZI, MM|B2B AM Development Batch 2 (Telkomsel)
AMIR FAUZI|AMAZE: Coaching Clinic Consultative Selling for AMEX Batch 1
RAMADHAN, SST., M.T.|AMAZE: Coaching Clinic Consultative Selling for AMEX Batch 2
ABDUL HAMID ARROZI, MM|Case Based Learning B2B Risk Management
AFDOL MUFTIASA|Leadership Development Program for Managers PT Telkom Akses
AGUS SOFIAN|Brevetisasi Logic Level 1 Batch 2
AKAS TRIONO HADI|Solution Enablement Produk Digital
AMIR FAUZI|Solution Enablement Produk Digital Batch 2
ANDI HAKIM KUSUMA|Internal Auditor Induction Program - Project Management
ANGGI AGUSTIAN|AMAZE: Coaching Clinic Consultative Selling for TREG 3 Batch 1
ARDISTYA WIRAWAN|AMAZE: Coaching Clinic Consultative Selling for TREG 3 Batch 2
ARI ADI YULIANTONO, M.ENG.|AMAZE: Coaching Clinic Consultative Selling for TREG 4
ARIF NURJAYANTO|B2B AM Development Program - BP IV, SAM, & Head Development Batch 1
ARYA PRADANA NUGRAHANDITO|Business Communication for AMEX TReg 1
AZIZAH KUSUMA WARDHANY|Case Based Learning B2B GRC Treg 1
... (list continues) ..."""
        rows = []
        for line in mapping_text.splitlines():
            if not line.strip():
                continue
            if "|" in line:
                n, a = line.split("|", 1)
            else:
                n, a = line.strip(), ""
            rows.append({"NAME": n.strip(), "ACTIVITY": a.strip()})
        pairs = pd.DataFrame(rows)

    pairs["NAME_UP"] = pairs["NAME"].astype(str).str.strip().str.upper()
    pairs["ACTIVITY_NORM"] = pairs["ACTIVITY"].apply(_norm_text)
    pairs = pairs.drop_duplicates(subset=["NAME_UP", "ACTIVITY_NORM"])
    return pairs[["NAME_UP", "ACTIVITY_NORM", "ACTIVITY"]]


def variation_page():
    """
    Streamlit page: two modes:
      - Upload file: user uploads single Excel (sheet 'General')
      - From Data Base: app fetches data from DB (learningImpact1)
    In both modes mapping file is optional (used to filter by name or event).
    """
    st.title("Parameter 3 — Poin Variasi Penugasan")
    st.markdown(
        "Pilih sumber data. Mode 'From Data Base' hanya mengambil data dari DB dan tidak menampilkan uploader untuk file utama. "
        "Mode 'Upload file' menerima satu file Excel (sheet 'General'). Mapping LIM1 optional (upload) — jika kosong gunakan built-in list."
    )

    source = st.radio("Data Resource", ["Upload file", "From Data Base"], index=0)

    uploaded = None
    mapfile = None

    if source == "Upload file":
        # single uploader for main file
        uploaded = st.file_uploader("Upload file (sheet 'General') — hanya 1 file", type=["xlsx", "xls"], key="var_main")
        mapfile = st.file_uploader("Optional: upload nameactlim1 (mapping LIM1)", type=["xlsx", "xls"], key="var_map")
        st.info("Mode Upload: unggah satu file Excel yang memuat sheet 'General'.")
    else:
        # DB mode: no main uploader shown, only optional mapping uploader
        st.info("Mode DB: data utama diambil dari database (view/table 'learningImpact1'). Upload hanya untuk mapping (opsional).")
        mapfile = st.file_uploader("Optional: upload nameactlim1 (mapping LIM1)", type=["xlsx", "xls"], key="var_map_db")

    # local fallback for convenience
    if source == "Upload file" and uploaded is None and os.path.exists("Agustus 2025.xlsx"):
        uploaded = "Agustus 2025.xlsx"
    if mapfile is None and os.path.exists("nameactlim1.xlsx"):
        mapfile = "nameactlim1.xlsx"

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

    mapping_df = _load_nameact_mapping(mapfile)
    if mapping_df is None or mapping_df.empty:
        st.error("Mapping LIM1 tidak valid atau kosong. Unggah file mapping atau gunakan built-in list.")
        return

    # detect columns in main table (col_nik detected but NOT displayed)
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
    # intentionally do NOT store NIK column for outputs
    # df_main["NIK"] = df_main[col_nik].astype(str).fillna("") if col_nik else ""

    # mapping sets
    lim1_names = set(mapping_df["NAME_UP"].tolist())
    mapping_activities = [a for a in mapping_df["ACTIVITY_NORM"].tolist() if a]

    def event_matches_any(ev_norm):
        if not isinstance(ev_norm, str) or ev_norm == "":
            return False
        for act in mapping_activities:
            if act and act in ev_norm:
                return True
        return False

    # include rows where name in list OR event matches any mapping activity
    df_filtered = df_main[df_main["NAME_UP"].isin(lim1_names) | df_main["EVENT_NORM"].apply(event_matches_any)].copy()
    if df_filtered.empty:
        st.warning("Tidak ada baris yang cocok berdasarkan nama OR event dari daftar mapping.")
        return

    st.subheader("Preview (filtered by mapping names OR mapping events)")
    preview_cols = [col_name, col_course]
    if col_sub:
        preview_cols.append(col_sub)
    if col_variasi:
        preview_cols.append(col_variasi)
    # intentionally do NOT include NIK in preview
    st.dataframe(df_filtered[preview_cols].head(200))

    # aggregate by expert + event (count frequency) and compute bobot from 'variasi'
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
            # NIK removed as requested
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

    st.subheader("Detail Variasi Penugasan (filtered)")
    # remove orange header styling; keep minimal padding and number formatting
    styler = (df_records[["no", "NAME", "EVENT", "BOBOT LH", "FREKUENSI", "POIN BOBOT"]]
              .style.set_table_styles([
                  {"selector": "th", "props": [("padding", "6px"), ("text-align", "left")]},
                  {"selector": "td", "props": [("padding", "6px")]}
              ]).format({"BOBOT LH": "{:.2f}", "POIN BOBOT": "{:.2f}"}))
    st.markdown(styler.to_html(), unsafe_allow_html=True)

    # summary per expert (group by NAME only, NIK removed)
    summary = (df_records
               .groupby(["NAME"], as_index=False)
               .agg(total_point=("POIN BOBOT", "sum"), total_freq=("FREKUENSI", "sum"))
               .sort_values("total_point", ascending=False))
    st.subheader("Ringkasan per Expert (Total Point)")
    st.dataframe(summary)

    max_point = st.number_input("Total Point Tertinggi (untuk normalisasi skor)", value=25.0, step=1.0)
    min_total_point = st.number_input("Minimal Total Point Expert (batas bawah)", value=1.0, step=0.1)

    summary["total_point_clamped"] = summary["total_point"].apply(lambda v: max(v, float(min_total_point)))
    summary["score_percent"] = (summary["total_point_clamped"] / float(max_point) * 100).clip(0, 100).round(2)

    st.subheader("Skor Normalisasi (Top 20)")
    st.dataframe(summary.head(20))

    # downloads (CSV won't include NIK)
    st.download_button("Download detail CSV", data=df_records.to_csv(index=False).encode("utf-8"), file_name="variation_detail.csv", mime="text/csv")
    st.download_button("Download summary CSV", data=summary.to_csv(index=False).encode("utf-8"), file_name="variation_summary.csv", mime="text/csv")

    # OpenAI analysis (best-effort)
    try:
        top3 = summary.head(3).to_dict(orient="records")
        prompt = ("Buat ringkasan singkat (3 kalimat) dan insight tentang top 3 expert berdasarkan total_point. "
                  f"Top3: {top3}")
        resp = genai.responses.create(model="models/text-bison-001", input=prompt)
        analysis = ""
        if hasattr(resp, "output") and getattr(resp, "output"):
            parts = []
            for out in resp.output:
                if hasattr(out, "content"):
                    for c in out.content:
                        parts.append(getattr(c, "text", str(c)))
            analysis = " ".join(parts).strip()
        else:
            analysis = str(resp)
        st.subheader("Analisis (OpenAI)")
        st.write(analysis)
    except Exception:
        st.info("Analisis OpenAI tidak tersedia (cek konfigurasi genai).")
# filepath: e:\CorpU\EXMAN\expert-calculator\modules\variation.py
# ...existing code...
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
    "article": 1.0
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


def _load_nameact_mapping(mfile):
    """
    Load mapping list (Name | Activity).
    If mfile provided, read first sheet and detect name/activity columns.
    Otherwise use built-in list provided by user.
    Returns DataFrame with columns: NAME_UP, ACTIVITY_NORM, ACTIVITY
    """
    if mfile is not None:
        try:
            if isinstance(mfile, (str, os.PathLike)) and os.path.exists(mfile):
                mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
            else:
                mp = pd.read_excel(mfile, sheet_name=0, dtype=str)
            mp = mp.rename(columns={c: c.strip() for c in mp.columns})
            name_col = _find_col(mp, ["name", "nama", "expert"])
            act_col = _find_col(mp, ["activity", "course_name", "course", "event"])
            if name_col is None and act_col is None:
                return None
            cols = []
            if name_col is not None:
                cols.append(name_col)
            if act_col is not None:
                cols.append(act_col)
            pairs = mp[cols].copy()
            rename_map = {}
            if name_col is not None:
                rename_map[name_col] = "NAME"
            if act_col is not None:
                rename_map[act_col] = "ACTIVITY"
            pairs = pairs.rename(columns=rename_map)
            if "NAME" not in pairs.columns:
                pairs["NAME"] = ""
            if "ACTIVITY" not in pairs.columns:
                pairs["ACTIVITY"] = ""
        except Exception:
            return None
    else:
        # built-in mapping (user-provided list). Keep trimmed.
        mapping_text = """ABDUL HAMID ARROZI, MM|B2B AM Development Batch 2 (Telkomsel)
AMIR FAUZI|AMAZE: Coaching Clinic Consultative Selling for AMEX Batch 1
RAMADHAN, SST., M.T.|AMAZE: Coaching Clinic Consultative Selling for AMEX Batch 2
ABDUL HAMID ARROZI, MM|Case Based Learning B2B Risk Management
AFDOL MUFTIASA|Leadership Development Program for Managers PT Telkom Akses
AGUS SOFIAN|Brevetisasi Logic Level 1 Batch 2
AKAS TRIONO HADI|Solution Enablement Produk Digital
AMIR FAUZI|Solution Enablement Produk Digital Batch 2
ANDI HAKIM KUSUMA|Internal Auditor Induction Program - Project Management
ANGGI AGUSTIAN|AMAZE: Coaching Clinic Consultative Selling for TREG 3 Batch 1
ARDISTYA WIRAWAN|AMAZE: Coaching Clinic Consultative Selling for TREG 3 Batch 2
ARI ADI YULIANTONO, M.ENG.|AMAZE: Coaching Clinic Consultative Selling for TREG 4
ARIF NURJAYANTO|B2B AM Development Program - BP IV, SAM, & Head Development Batch 1
ARYA PRADANA NUGRAHANDITO|Business Communication for AMEX TReg 1
AZIZAH KUSUMA WARDHANY|Case Based Learning B2B GRC Treg 1
... (list continues) ..."""
        rows = []
        for line in mapping_text.splitlines():
            if not line.strip():
                continue
            if "|" in line:
                n, a = line.split("|", 1)
            else:
                n, a = line.strip(), ""
            rows.append({"NAME": n.strip(), "ACTIVITY": a.strip()})
        pairs = pd.DataFrame(rows)

    pairs["NAME_UP"] = pairs["NAME"].astype(str).str.strip().str.upper()
    pairs["ACTIVITY_NORM"] = pairs["ACTIVITY"].apply(_norm_text)
    pairs = pairs.drop_duplicates(subset=["NAME_UP", "ACTIVITY_NORM"])
    return pairs[["NAME_UP", "ACTIVITY_NORM", "ACTIVITY"]]


def variation_page():
    """
    Streamlit page: two modes:
      - Upload file: user uploads single Excel (sheet 'General')
      - From Data Base: app fetches data from DB (learningImpact1)
    In both modes mapping file is optional (used to filter by name or event).
    """
    st.title("Parameter 3 — Poin Variasi Penugasan")
    st.markdown(
        "Pilih sumber data. Mode 'From Data Base' hanya mengambil data dari DB dan tidak menampilkan uploader untuk file utama. "
        "Mode 'Upload file' menerima satu file Excel (sheet 'General'). Mapping LIM1 optional (upload) — jika kosong gunakan built-in list."
    )

    source = st.radio("Data Resource", ["Upload file", "From Data Base"], index=0)

    uploaded = None
    mapfile = None

    if source == "Upload file":
        # single uploader for main file
        uploaded = st.file_uploader("Upload file (sheet 'General') — hanya 1 file", type=["xlsx", "xls"], key="var_main")
        mapfile = st.file_uploader("Optional: upload nameactlim1 (mapping LIM1)", type=["xlsx", "xls"], key="var_map")
        st.info("Mode Upload: unggah satu file Excel yang memuat sheet 'General'.")
    else:
        # DB mode: no main uploader shown, only optional mapping uploader
        st.info("Mode DB: data utama diambil dari database (view/table 'learningImpact1'). Upload hanya untuk mapping (opsional).")
        mapfile = st.file_uploader("Optional: upload nameactlim1 (mapping LIM1)", type=["xlsx", "xls"], key="var_map_db")

    # local fallback for convenience
    if source == "Upload file" and uploaded is None and os.path.exists("Agustus 2025.xlsx"):
        uploaded = "Agustus 2025.xlsx"
    if mapfile is None and os.path.exists("nameactlim1.xlsx"):
        mapfile = "nameactlim1.xlsx"

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

    mapping_df = _load_nameact_mapping(mapfile)
    if mapping_df is None or mapping_df.empty:
        st.error("Mapping LIM1 tidak valid atau kosong. Unggah file mapping atau gunakan built-in list.")
        return

    # detect columns in main table (col_nik detected but NOT displayed)
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
    # intentionally do NOT store NIK column for outputs
    # df_main["NIK"] = df_main[col_nik].astype(str).fillna("") if col_nik else ""

    # mapping sets
    lim1_names = set(mapping_df["NAME_UP"].tolist())
    mapping_activities = [a for a in mapping_df["ACTIVITY_NORM"].tolist() if a]

    def event_matches_any(ev_norm):
        if not isinstance(ev_norm, str) or ev_norm == "":
            return False
        for act in mapping_activities:
            if act and act in ev_norm:
                return True
        return False

    # include rows where name in list OR event matches any mapping activity
    df_filtered = df_main[df_main["NAME_UP"].isin(lim1_names) | df_main["EVENT_NORM"].apply(event_matches_any)].copy()
    if df_filtered.empty:
        st.warning("Tidak ada baris yang cocok berdasarkan nama OR event dari daftar mapping.")
        return

    st.subheader("Preview (filtered by mapping names OR mapping events)")
    preview_cols = [col_name, col_course]
    if col_sub:
        preview_cols.append(col_sub)
    if col_variasi:
        preview_cols.append(col_variasi)
    # intentionally do NOT include NIK in preview
    st.dataframe(df_filtered[preview_cols].head(200))

    # aggregate by expert + event (count frequency) and compute bobot from 'variasi'
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
            # NIK removed as requested
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

    st.subheader("Detail Variasi Penugasan (filtered)")
    # remove orange header styling; keep minimal padding and number formatting
    styler = (df_records[["no", "NAME", "EVENT", "BOBOT LH", "FREKUENSI", "POIN BOBOT"]]
              .style.set_table_styles([
                  {"selector": "th", "props": [("padding", "6px"), ("text-align", "left")]},
                  {"selector": "td", "props": [("padding", "6px")]}
              ]).format({"BOBOT LH": "{:.2f}", "POIN BOBOT": "{:.2f}"}))
    st.markdown(styler.to_html(), unsafe_allow_html=True)

    # summary per expert (group by NAME only, NIK removed)
    summary = (df_records
               .groupby(["NAME"], as_index=False)
               .agg(total_point=("POIN BOBOT", "sum"), total_freq=("FREKUENSI", "sum"))
               .sort_values("total_point", ascending=False))
    st.subheader("Ringkasan per Expert (Total Point)")
    st.dataframe(summary)

    max_point = st.number_input("Total Point Tertinggi (untuk normalisasi skor)", value=25.0, step=1.0)
    min_total_point = st.number_input("Minimal Total Point Expert (batas bawah)", value=1.0, step=0.1)

    summary["total_point_clamped"] = summary["total_point"].apply(lambda v: max(v, float(min_total_point)))
    summary["score_percent"] = (summary["total_point_clamped"] / float(max_point) * 100).clip(0, 100).round(2)

    st.subheader("Skor Normalisasi (Top 20)")
    st.dataframe(summary.head(20))

    # downloads (CSV won't include NIK)
    st.download_button("Download detail CSV", data=df_records.to_csv(index=False).encode("utf-8"), file_name="variation_detail.csv", mime="text/csv")
    st.download_button("Download summary CSV", data=summary.to_csv(index=False).encode("utf-8"), file_name="variation_summary.csv", mime="text/csv")

    # OpenAI analysis (best-effort)
    try:
        top3 = summary.head(3).to_dict(orient="records")
        prompt = ("Buat ringkasan singkat (3 kalimat) dan insight tentang top 3 expert berdasarkan total_point. "
                  f"Top3: {top3}")
        resp = genai.responses.create(model="models/text-bison-001", input=prompt)
        analysis = ""
        if hasattr(resp, "output") and getattr(resp, "output"):
            parts = []
            for out in resp.output:
                if hasattr(out, "content"):
                    for c in out.content:
                        parts.append(getattr(c, "text", str(c)))
            analysis = " ".join(parts).strip()
        else:
            analysis = str(resp)
        st.subheader("Analisis (OpenAI)")
        st.write(analysis)
    except Exception:
        st.info("Analisis OpenAI tidak tersedia (cek konfigurasi genai).")