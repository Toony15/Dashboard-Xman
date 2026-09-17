import re

import pandas as pd
import streamlit as st

from dataManager import load_all_data
from dbConfig import get_db_connection

BOBOT_SCHEME = [
    (0, 200_000_000, 0.0, 5.0),                  # Rp0 - Rp200 juta
    (200_000_000, 1_000_000_000, 5.1, 10.0),     # Rp200 juta - Rp1 miliar
    (1_000_000_000, 5_000_000_000, 10.1, 15.0),  # Rp1 miliar - Rp5 miliar
]
BOBOT_MAKSIMAL = BOBOT_SCHEME[-1][3]  # > Rp5 miliar dibatasi (capped) di sini


KOLOM_DIBUTUHKAN = {
    "nik": ["NIK"],
    "expert": ["NAMA"],
    "assignment": ["ASSIGNMENT"],
    "financial_eksisting": ["FINANCIAL", "EKSISTING"],
    "potensi_revenue": ["POT", "REVENUE"],
}
LABEL_KOLOM = {
    "nik": "NIK",
    "expert": "Nama Expert",
    "assignment": "Assignment/Penugasan",
    "financial_eksisting": "Revenue Eksisting (per Assignment)",
    "potensi_revenue": "Potensi Revenue Tambahan (per Assignment)",
    "total_financial_eksisting": "Total Revenue Eksisting (Semua Assignment)",
    "hasil_impact_expert": "Hasil Impact Expert (%)",
    "jumlah_assignment": "Jumlah Assignment",
}

# Kolom yang jadi kunci pengelompokan "satu assignment milik satu expert".
KUNCI_ASSIGNMENT = ["nik", "expert", "assignment"]
KUNCI_EXPERT = ["nik", "expert"]

RUPIAH_PREFIX_RE = re.compile(r"(?i)^rp\.?")

# Nama tabel & kolom aktual di Supabase (schema public.expert_impact) berbeda
# dari nama internal yang dipakai kode ini. Mapping ini menyamakannya saat
# baca dari database, supaya tidak perlu ALTER TABLE ke data yang sudah ada.
NAMA_TABEL_DB = "expert_impact"
KOLOM_DB_KE_INTERNAL = {
    "customer": "assignment",
    "pot_revenue_tambahan": "potensi_revenue",
}

# ---------------------------------------------------------------------------
# Util angka & teks
# ---------------------------------------------------------------------------
def hitung_bobot_impact(nilai):
    """Hitung Bobot Impact Expert (persen, 0-15) dari total Financial Eksisting."""
    if pd.isna(nilai) or nilai <= 0:
        return 0.0
    for batas_bawah, batas_atas, bobot_bawah, bobot_atas in BOBOT_SCHEME:
        if nilai <= batas_atas:
            proporsi = (nilai - batas_bawah) / (batas_atas - batas_bawah)
            return bobot_bawah + proporsi * (bobot_atas - bobot_bawah)
    return BOBOT_MAKSIMAL


def _parse_rupiah(value):
    """
    Ubah teks nominal rupiah mentah jadi float.

    File sumber punya beberapa gaya penulisan yang harus ditangani:
      - "396000000.00"        -> format polos, titik = desimal
      - "Rp32.313.000.000"    -> format ID, titik = pemisah ribuan
      - "Rp.17.820.000"       -> prefix "Rp." + titik ribuan
      - "Rp. 100.000.000,-"   -> akhiran ",-" khas penulisan rupiah
    """
    if pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text or text == "-":
        return 0.0

    text = text.replace(" ", "")
    text = RUPIAH_PREFIX_RE.sub("", text)
    text = text.rstrip(",-")
    text = text.strip(".")
    if not text:
        return 0.0

    if "," in text and "." in text:
        # Format Indonesia: titik = ribuan, koma = desimal.
        text = text.replace(".", "").replace(",", ".")
    elif text.count(".") > 1:
        # Lebih dari satu titik -> semuanya pemisah ribuan (mis. Rp32.313.000.000).
        text = text.replace(".", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        if head and len(tail) in (1, 2):
            text = f"{head.replace(',', '')}.{tail}"
        else:
            text = text.replace(",", "")
    # Sisanya (satu titik tunggal) dianggap desimal, mis. "396000000.00".

    try:
        return float(text)
    except ValueError:
        return 0.0


def _format_rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")


def _normalize_header(value):
    if pd.isna(value):
        return ""
    return " ".join(str(value).upper().split())


def _clean_text(value):
    """Rapikan teks sel: gabung jadi satu baris & buang spasi berlebih."""
    if pd.isna(value):
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _clean_nik(value):
    """Rapikan NIK: rapikan teks & buang akhiran '.0' sisa konversi Excel."""
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]
    return cleaned


# ---------------------------------------------------------------------------
# Deteksi kolom dari header
# ---------------------------------------------------------------------------
def _find_column(headers, required_substrings):
    """Cari index kolom yang header-nya (sudah dinormalisasi) memuat SEMUA substring."""
    for idx, header in enumerate(headers):
        if all(sub in header for sub in required_substrings):
            return idx
    return None


def _locate_columns(headers):
    """
    Cari index tiap kolom di KOLOM_DIBUTUHKAN berdasarkan kata kunci header.
    Return: (dict nama_kolom -> index, list nama_kolom yang tidak ketemu)
    """
    found, missing = {}, []
    for name, keywords in KOLOM_DIBUTUHKAN.items():
        idx = _find_column(headers, keywords)
        if idx is None:
            missing.append(name)
        else:
            found[name] = idx
    return found, missing


def _detect_header_rows(raw):
    """
    Deteksi otomatis jumlah baris header di file mentah. Mendukung 2 gaya
    template yang pernah dipakai:
      - 1 baris header polos, mis. 'NIK, NAMA LENGKAP EXPERT, ASSIGNMENT, ...'
      - 2 baris header ber-merged-cell (template lama), baris ke-1 = judul
        besar seperti 'IMPACT', baris ke-2 = sub-judul seperti
        'FINANCIAL EKSISTING'.

    Coba versi 1-baris dulu; kalau masih ada kolom wajib yang tidak ketemu,
    coba versi gabungan 2-baris dan pakai mana yang paling lengkap.
    """
    headers_1baris = [_normalize_header(v) for v in raw.iloc[0]]
    _, missing_1 = _locate_columns(headers_1baris)
    if not missing_1:
        return headers_1baris, 1

    if len(raw) > 1:
        headers_2baris = [
            _normalize_header(sub_header) or _normalize_header(top_header)
            for top_header, sub_header in zip(raw.iloc[0], raw.iloc[1])
        ]
        _, missing_2 = _locate_columns(headers_2baris)
        if len(missing_2) < len(missing_1):
            return headers_2baris, 2

    return headers_1baris, 1


# ---------------------------------------------------------------------------
# Parsing file mentah
# ---------------------------------------------------------------------------
def _isi_identitas_bersambung(df):
    """(Tidak dipakai lagi - lihat _parse_satu_file untuk logika terbaru)."""
    raise NotImplementedError


def _parse_satu_file(uploaded_file, quarter_upload):
    """
    Parse satu file mentah jadi baris (NIK, Expert, Assignment, nominal).

    ATURAN PENTING (sesuai cara pencatatan di file sumber): satu sel
    ASSIGNMENT adalah merged cell yang menaungi sekelompok expert + beberapa
    baris nominal Financial Eksisting / Potensi Revenue. Nominal-nominal itu
    adalah milik SATU assignment itu secara keseluruhan - BUKAN milik expert
    yang kebetulan namanya sebaris dengan angka tersebut. Karena itu:
      1. Semua nominal dalam satu blok assignment dijumlahkan jadi satu
         "total assignment".
      2. Total itu diberikan PENUH (bukan dibagi) ke SETIAP expert yang
         tercatat mengikuti assignment tersebut.
    """
    reader = pd.read_csv if uploaded_file.name.lower().endswith(".csv") else pd.read_excel
    raw = reader(uploaded_file, header=None, dtype=str)

    if len(raw) < 3:
        st.warning(f"File {uploaded_file.name} tidak punya cukup baris data.")
        return None

    headers, n_header_rows = _detect_header_rows(raw)
    columns, missing = _locate_columns(headers)
    if missing:
        st.error(
            f"Kolom berikut tidak ditemukan di {uploaded_file.name}: "
            f"{', '.join(LABEL_KOLOM.get(m, m) for m in missing)}. "
            f"Header yang terbaca: {headers}"
        )
        return None

    data = raw.iloc[n_header_rows:].reset_index(drop=True)
    baris = pd.DataFrame({
        "nik_baris": data[columns["nik"]].apply(_clean_nik),
        "expert_baris": data[columns["expert"]].apply(_clean_text),
        "assignment_baris": data[columns["assignment"]].apply(_clean_text),
        "financial_eksisting": data[columns["financial_eksisting"]].apply(_parse_rupiah),
        "potensi_revenue": data[columns["potensi_revenue"]].apply(_parse_rupiah),
    })

    assignment_baru = baris["assignment_baris"].notna()
    if len(assignment_baru) and not assignment_baru.iloc[0]:
        assignment_baru.iloc[0] = True  # jaga-jaga baris pertama file kosong
    baris["blok_assignment"] = assignment_baru.cumsum()
    baris["assignment"] = baris["assignment_baris"].ffill()

    # --- Total nominal per blok (per assignment), dari SEMUA baris di blok -
    total_per_blok = baris.groupby("blok_assignment", as_index=False).agg(
        assignment=("assignment", "first"),
        financial_eksisting=("financial_eksisting", "sum"),
        potensi_revenue=("potensi_revenue", "sum"),
    )

    ada_identitas = baris["nik_baris"].notna() | baris["expert_baris"].notna()
    peserta = baris.loc[ada_identitas, ["blok_assignment", "nik_baris", "expert_baris"]].copy()
    peserta["nik"] = pd.to_numeric(peserta["nik_baris"], errors="coerce")
    peserta = peserta.dropna(subset=["nik", "expert_baris"])
    peserta = peserta.drop_duplicates(subset=["blok_assignment", "nik"])
    peserta = peserta.rename(columns={"expert_baris": "expert"})[["blok_assignment", "nik", "expert"]]

    # --- Setiap peserta mendapat nominal PENUH dari assignment yang -------
    #     diikutinya bersama (bukan dibagi rata).
    hasil = peserta.merge(total_per_blok, on="blok_assignment", how="left")
    hasil["quarter"] = quarter_upload
    return hasil[["nik", "expert", "assignment", "financial_eksisting", "potensi_revenue", "quarter"]]


def read_and_merge(files, quarter_upload):
    """Baca & gabungkan semua file upload jadi satu tabel baris-mentah."""
    all_rows = []
    for uploaded_file in files:
        try:
            df = _parse_satu_file(uploaded_file, quarter_upload)
        except Exception as e:
            st.error(f"Gagal membaca file {uploaded_file.name}: {e}")
            continue
        if df is not None and not df.empty:
            all_rows.append(df)

    if not all_rows:
        return pd.DataFrame()

    combined = pd.concat(all_rows, ignore_index=True)
    combined["expert"] = combined.groupby("nik")["expert"].transform("first")
    return combined


# ---------------------------------------------------------------------------
# Perhitungan skor
# ---------------------------------------------------------------------------
def build_assignment_table(df):
    """
    Rangkum data mentah jadi SATU baris per (NIK, Expert, Assignment).

    Nominal per (nik, expert) untuk satu assignment yang sama sudah berupa
    total penuh assignment tersebut sejak tahap parsing (lihat
    `_parse_satu_file`), jadi di sini cukup dijumlahkan untuk berjaga-jaga
    kalau ada assignment dengan nama sama yang muncul lebih dari satu kali
    untuk expert yang sama (mis. dari file quarter yang berbeda).
    """
    return df.groupby(KUNCI_ASSIGNMENT, as_index=False, dropna=False).agg(
        financial_eksisting=("financial_eksisting", "sum"),
        potensi_revenue=("potensi_revenue", "sum"),
    )


def compute_impact_scores(assignment_df):
    """
    Jumlahkan Financial Eksisting & Potensi Revenue dari SEMUA assignment
    milik tiap expert, lalu hitung Hasil Impact Expert dari total tersebut.
    Potensi Revenue Tambahan hanya informasi, tidak memengaruhi skor.
    """
    summary = assignment_df.groupby(KUNCI_EXPERT, as_index=False, dropna=False).agg(
        financial_eksisting=("financial_eksisting", "sum"),
        potensi_revenue=("potensi_revenue", "sum"),
        jumlah_assignment=("assignment", "nunique"),
    )
    summary["hasil_impact_expert"] = summary["financial_eksisting"].apply(hitung_bobot_impact).round(3)
    return summary.sort_values("financial_eksisting", ascending=False).reset_index(drop=True)


def build_impact_detail_table(assignment_df, summary):
    """
    Gabungkan tabel per-assignment dengan total & skor per expert, supaya
    tiap baris assignment ikut menampilkan Total Financial Eksisting dan
    Hasil Impact Expert milik expert tersebut (diulang di tiap barisnya).

    Expert diurutkan dari Total Financial Eksisting terbesar ke terkecil;
    di dalam satu expert, assignment diurutkan dari nominal terbesar.
    """
    detail = assignment_df.merge(
        summary[KUNCI_EXPERT + ["financial_eksisting", "hasil_impact_expert"]].rename(
            columns={"financial_eksisting": "total_financial_eksisting"}
        ),
        on=KUNCI_EXPERT,
        how="left",
    )

    urutan_expert = summary.apply(lambda r: (r["nik"], r["expert"]), axis=1).tolist()
    detail["_urutan_expert"] = pd.Categorical(
        list(zip(detail["nik"], detail["expert"])), categories=urutan_expert, ordered=True
    )
    detail = (
        detail.sort_values(["_urutan_expert", "financial_eksisting"], ascending=[True, False])
        .drop(columns="_urutan_expert")
        .reset_index(drop=True)
    )

    return detail[
        ["nik", "expert", "assignment", "financial_eksisting", "potensi_revenue",
         "total_financial_eksisting", "hasil_impact_expert"]
    ]


def save_scores_to_db(supabase, summary, quarter):
    """Upsert Hasil Impact Expert tiap expert ke tabel 'calculated'. Return jumlah baris."""
    for _, row in summary.iterrows():
        supabase.table("calculated").upsert(
            {
                "nik": int(row["nik"]),
                "expert": row["expert"],
                "quarter": quarter,
                "impact_expert": float(row["hasil_impact_expert"]),
            },
            on_conflict="nik,expert,quarter",
        ).execute()
    return len(summary)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
def _render_detail_table(assignment_df, summary):
    st.subheader("📋 Rincian Assignment per Expert")
    st.caption(
        "Setiap baris = satu assignment yang diikuti expert (nominal dari "
        "beberapa baris sumber untuk assignment yang sama sudah dijumlahkan). "
        "'Total Revenue Eksisting' dan 'Hasil Impact Expert (%)' adalah "
        "angka akhir milik expert tersebut, diulang di setiap barisnya."
    )
    detail_display = build_impact_detail_table(assignment_df, summary).copy()
    for col in ["financial_eksisting", "potensi_revenue", "total_financial_eksisting"]:
        detail_display[col] = detail_display[col].apply(_format_rupiah)
    st.dataframe(
        detail_display.rename(columns=LABEL_KOLOM),
        use_container_width=True,
        hide_index=True,
    )


def _render_excel_download(assignment_df, summary, quarter):
    """Tombol download Excel berisi 2 sheet: rincian per assignment & rekap per expert."""
    if st.button("Download Hasil Impact Expert (Excel)", key="btn_download_impact"):
        detail_download = build_impact_detail_table(assignment_df, summary).rename(columns=LABEL_KOLOM)
        rekap_download = summary.rename(columns=LABEL_KOLOM)

        import io
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            detail_download.to_excel(writer, sheet_name="Detail", index=False)
            rekap_download.to_excel(writer, sheet_name="Rekap", index=False)

        buffer.seek(0)

        st.download_button(
            label="Download Impact_Expert.xlsx",
            data=buffer,
            file_name=f"Impact_Expert_{quarter}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


def _render_summary_table(summary):
    st.subheader("📊 Rekap Impact Expert per Expert")
    display_df = summary.copy()
    for col in ["financial_eksisting", "potensi_revenue"]:
        display_df[col] = display_df[col].apply(_format_rupiah)
    st.dataframe(display_df.rename(columns=LABEL_KOLOM), use_container_width=True, hide_index=True)

    st.download_button(
        "Download rekap CSV",
        data=summary.rename(columns=LABEL_KOLOM).to_csv(index=False).encode("utf-8"),
        file_name="impact_expert_summary.csv",
        mime="text/csv",
    )


def ImpactExpert():
    supabase = get_db_connection()

    st.title("💥 Impact Expert")
    st.caption(
        "Mengukur dampak expert dari kegiatan yang menghasilkan revenue ke perusahaan. "
        "Nominal 'Revenue Eksisting' dijumlahkan dulu per assignment, lalu dijumlahkan "
        "lagi lintas-assignment per expert, baru dimasukkan ke skema Bobot bertingkat "
        "(0% - 15%). 'Potensi Revenue Tambahan' hanya informasi tambahan dan TIDAK "
        "memengaruhi skor. Expert yang tidak punya NIK (dianggap eksternal) tidak "
        "ditampilkan sama sekali."
    )

    mode = st.pills(
        "Data Resource", ["Upload file", "From Data Base"],
        selection_mode="single", default="From Data Base",
    )

    if mode == "Upload file":
        st.header("📁 Upload File")
        quarter_upload = st.selectbox("Quarter untuk data ini", ["Q1", "Q2", "Q3", "Q4"])
        uploaded_files = st.file_uploader(
            "Upload data Impact Expert (format Excel/CSV)",
            accept_multiple_files=True,
            type=["xls", "xlsx", "csv"],
        )
        if uploaded_files:
            st.session_state["impact_combined_df"] = read_and_merge(uploaded_files, quarter_upload)
            st.session_state["impact_quarter"] = quarter_upload
        combined_df = st.session_state.get("impact_combined_df", pd.DataFrame())
        quarter = st.session_state.get("impact_quarter", quarter_upload)
    else:
        combined_df = load_all_data(NAMA_TABEL_DB)
        if not combined_df.empty:
            combined_df = combined_df.rename(columns=KOLOM_DB_KE_INTERNAL)

    if combined_df.empty:
        st.info("Tidak terdapat data")
        return

    if mode == "From Data Base":
        quarter = st.pills(
            "Pilih Quarter", ["Q1", "Q2", "Q3", "Q4"], selection_mode="single", default="Q1"
        )
        if "quarter" in combined_df.columns:
            combined_df = combined_df[combined_df["quarter"] == quarter]

    if combined_df.empty:
        st.info(f"Tidak ada data untuk {quarter}. Pilih quarter lain yang sesuai dengan data.")
        return

    # Fallback untuk data lama di DB yang belum punya kolom 'assignment'.
    if "assignment" not in combined_df.columns:
        combined_df["assignment"] = "-"

    missing_cols = [
        c for c in ["nik", "expert", "assignment", "financial_eksisting", "potensi_revenue"]
        if c not in combined_df.columns
    ]
    if missing_cols:
        st.error(f"Kolom berikut tidak ditemukan: {missing_cols}.")
        return

    assignment_df = build_assignment_table(combined_df)
    summary = compute_impact_scores(assignment_df)

    col1, col2 = st.columns(2)
    col1.metric("Total Expert", len(summary), border=True)
    col2.metric("Total Revenue Eksisting", _format_rupiah(summary["financial_eksisting"].sum()), border=True)

    _render_detail_table(assignment_df, summary)
    _render_summary_table(summary)
    _render_excel_download(assignment_df, summary, quarter)

    if st.button("💾 Simpan Impact Expert Score ke Database", key="btn_save_impact"):
        try:
            count = save_scores_to_db(supabase, summary, quarter)
            st.session_state["impact_save_message"] = (
                f"✅ {count} data disimpan/diupdate untuk {quarter}"
            )
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")

    if "impact_save_message" in st.session_state:
        st.success(st.session_state.pop("impact_save_message"))


if __name__ == "__main__":
    ImpactExpert()