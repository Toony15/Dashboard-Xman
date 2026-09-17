import io

import pandas as pd
import plotly.express as px
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection

CATEGORY_BOBOT = {
    "Teaching": 1.5,
    "Expert Insight (Pembicara)": 1.4,
    "Learning Content Designer/Developer": 1.4,
    "Coaching (Coach)": 1.3,
    "Mentoring (Mentor)": 1.3,
    "Penguji/Assessor": 1.3,
}

KATEGORI_ORDER = list(CATEGORY_BOBOT.keys())

WEIGHT_GROUP = {
    "Teaching": "Teaching",
    "Expert Insight (Pembicara)": "Expert Insight (Pembicara)",
    "Learning Content Designer/Developer": "Learning Content Designer/Developer",
    "Coaching (Coach)": "Coaching/Mentoring",
    "Mentoring (Mentor)": "Coaching/Mentoring",
    "Penguji/Assessor": "Penguji/Assessor",
}

WEIGHT_GROUP_BOBOT = {
    "Teaching": 1.5,
    "Expert Insight (Pembicara)": 1.4,
    "Learning Content Designer/Developer": 1.4,
    "Coaching/Mentoring": 1.3,
    "Penguji/Assessor": 1.3,
}

TOTAL_BOBOT_ASSIGNMENT = sum(WEIGHT_GROUP_BOBOT.values())  # = 6.9

VARIASI_PERSEN = 30

# Nilai mentah di kolom "activities" -> kategori tampilan (1:1, tidak digabung)
ACTIVITY_TO_CATEGORY = {
    "teaching": "Teaching",
    "expert insight (pembicara)": "Expert Insight (Pembicara)",
    "learning content designer/developer": "Learning Content Designer/Developer",
    "coaching (coach)": "Coaching (Coach)",
    "mentoring (mentor)": "Mentoring (Mentor)",
    "penguji/assessor": "Penguji/Assessor",
}


def _map_activity(raw_value):
    if pd.isna(raw_value):
        return None
    return ACTIVITY_TO_CATEGORY.get(str(raw_value).strip().lower())


def read_and_merge(files, quarter_upload):
    """
    Parser file raw 'LH Recog/Request' (sheet 'direct,coe,self') - sama seperti
    learningHour.py & expertLevel.py, karena memang sumber file mentahnya SAMA.
    Di sini kita cuma butuh nik, expert (dari 'name'), dan activities.
    """
    all_data = []

    column_mapping = {
        "nik": "nik",
        "name": "expert",
        "activities": "activities",
    }

    for uploaded_file in files:
        try:
            df = pd.read_excel(uploaded_file, sheet_name="direct,coe,self")
        except ValueError:
            xls = pd.ExcelFile(uploaded_file)
            st.error(
                f"Sheet 'direct,coe,self' tidak ditemukan di {uploaded_file.name}. "
                f"Sheet yang tersedia: {xls.sheet_names}"
            )
            continue
        except Exception as e:
            st.error(f"Gagal membaca file {uploaded_file.name}: {e}")
            continue

        df.columns = [str(c).strip().lower() for c in df.columns]

        missing = [c for c in column_mapping if c not in df.columns]
        if missing:
            st.warning(f"Kolom berikut tidak ditemukan di {uploaded_file.name}: {missing}")
            continue

        df = df.rename(columns=column_mapping)
        df["quarter"] = quarter_upload
        all_data.append(df)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()


def compute_variasi_score(df):
    """
    Hitung skor Variasi Penugasan per expert sesuai rumus resmi:

    1. Untuk tiap expert, tentukan APAKAH dia PERNAH mengerjakan tiap satu dari 5
       KELOMPOK BOBOT resmi minimal 1x - status ya/tidak (biner), BUKAN dihitung
       berapa kali repetisinya (3x Teaching tetap dihitung 1x "pernah Teaching",
       dan Coaching + Mentoring dianggap 1 kelompok yang sama).
    2. n_frekuensi_expert = jumlah BOBOT dari kelompok-kelompok yang PERNAH
       dikerjakan (masing-masing kelompok kontribusi bobotnya cuma sekali).
    3. Variasi Score = (n_frekuensi_expert / TOTAL_BOBOT_ASSIGNMENT) x 30%

    Catatan: kategori TAMPILAN (kolom 'kategori') tetap 6 jenis apa adanya di
    Excel (Coaching & Mentoring terpisah). Hanya untuk perhitungan skor, mereka
    dikelompokkan lewat WEIGHT_GROUP supaya tidak dihitung dobel.

    Return: (summary per expert, detail kategori per expert [tampilan, 6 jenis],
    list nilai activities yang tidak dikenali/tidak masuk kategori resmi)
    """
    work = df.copy()
    work["kategori"] = work["activities"].apply(_map_activity)
    work["kelompok_bobot"] = work["kategori"].map(WEIGHT_GROUP)

    unmapped_values = sorted(
        work.loc[work["kategori"].isna() & work["activities"].notna(), "activities"]
        .astype(str)
        .unique()
        .tolist()
    )

    mapped = work.dropna(subset=["kategori"])

    # Detail per kategori TAMPILAN (6 jenis) - dipakai untuk tabel detail & chart
    touched = (
        mapped.groupby(["expert", "kategori"]).size().reset_index(name="jumlah_kejadian")
    )
    touched["bobot_kategori"] = touched["kategori"].map(CATEGORY_BOBOT)

    # Detail per KELOMPOK BOBOT (5 kelompok) - khusus untuk hitung skor,
    # supaya Coaching (Coach) + Mentoring (Mentor) tidak dihitung dobel
    touched_group = (
        mapped.groupby(["expert", "kelompok_bobot"])
        .size()
        .reset_index(name="jumlah_kejadian_kelompok")
    )
    touched_group["bobot_kelompok"] = touched_group["kelompok_bobot"].map(WEIGHT_GROUP_BOBOT)

    summary = touched_group.groupby("expert", as_index=False).agg(
        n_frekuensi_expert=("bobot_kelompok", "sum"),
        jumlah_kategori_dikerjakan=("kelompok_bobot", "nunique"),
    )
    nik_per_expert = df.groupby("expert")["nik"].first().reset_index()
    summary = summary.merge(nik_per_expert, on="expert", how="left")

    summary["variasi_score"] = (
        (summary["n_frekuensi_expert"] / TOTAL_BOBOT_ASSIGNMENT) * VARIASI_PERSEN
    ).round(2)
    summary = summary.sort_values("variasi_score", ascending=False).reset_index(drop=True)

    return summary, touched, unmapped_values


def build_individual_assignment_table(df, summary):
    """
    Bangun tabel detail per KEJADIAN assignment (bukan digabung/dihitung jumlahnya).

    Urutan barisnya:
    1. Expert diurutkan dari yang PALING BANYAK assignment ke yang PALING SEDIKIT
       (bukan alfabetis/NIK), supaya expert paling aktif tampil paling atas.
    2. Di dalam satu expert, kategori diurutkan sesuai urutan resmi di CATEGORY_BOBOT
       (Teaching dulu, lalu Expert Insight, Learning Content, Coaching, Mentoring,
       baru Penguji/Assessor).

    Kolom yang disertakan di tiap baris:
    - Bobot Assignment       : bobot KATEGORI TAMPILAN pada baris itu (6 jenis)
    - Jumlah Assignment (Jenis Ini) : berapa kali expert ini mengerjakan KATEGORI YANG
      SAMA (misal Teaching = 3), diulang di setiap baris kategori yang sama
    - Total Assignment Expert : total SELURUH assignment expert ini (semua kategori
      digabung), diulang di setiap baris milik expert tersebut
    - Skor Variasi Expert    : skor akhir expert tersebut dari `summary`, diulang di
      setiap barisnya
    """
    work = df.copy()
    work["kategori"] = work["activities"].apply(_map_activity)

    mapped = work.dropna(subset=["kategori"]).copy()
    mapped["bobot_assignment"] = mapped["kategori"].map(CATEGORY_BOBOT)

    # Jumlah kejadian per (expert, kategori) -> berapa kali expert dapat JENIS ini
    jumlah_per_expert_kategori = (
        mapped.groupby(["expert", "kategori"])
        .size()
        .rename("jumlah_kejadian_jenis")
        .reset_index()
    )
    mapped = mapped.merge(jumlah_per_expert_kategori, on=["expert", "kategori"], how="left")

    # Total seluruh assignment per expert (semua jenis digabung)
    total_per_expert = (
        mapped.groupby("expert").size().rename("total_assignment_expert").reset_index()
    )
    mapped = mapped.merge(total_per_expert, on="expert", how="left")

    # Urutan expert: dari yang paling banyak assignment ke paling sedikit
    expert_order = total_per_expert.sort_values(
        "total_assignment_expert", ascending=False
    )["expert"].tolist()
    mapped["expert"] = pd.Categorical(mapped["expert"], categories=expert_order, ordered=True)

    mapped["kategori"] = pd.Categorical(
        mapped["kategori"], categories=KATEGORI_ORDER, ordered=True
    )

    sorted_df = mapped.sort_values(["expert", "kategori"]).reset_index(drop=True)
    result = sorted_df.merge(summary[["expert", "variasi_score"]], on="expert", how="left")

    return result[
        [
            "nik", "expert", "kategori", "bobot_assignment",
            "jumlah_kejadian_jenis", "total_assignment_expert", "variasi_score",
        ]
    ].rename(
        columns={
            "nik": "NIK",
            "expert": "Expert",
            "kategori": "Jenis Assignment",
            "bobot_assignment": "Bobot Assignment",
            "jumlah_kejadian_jenis": "Jumlah Assignment (Jenis Ini)",
            "total_assignment_expert": "Total Assignment Expert",
            "variasi_score": "Skor Variasi Expert",
        }
    )


def _render_excel_download(detail_display, summary_display, quarter):
    """Tombol download Excel berisi 2 sheet: detail per-assignment & rekap per expert."""
    if st.button("Download Hasil Variasi (Excel)", key="btn_download_variasi_excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            detail_display.to_excel(writer, sheet_name="Detail", index=False)
            summary_display.to_excel(writer, sheet_name="Rekap", index=False)
        buffer.seek(0)

        st.download_button(
            label="Download Variasi_Penugasan.xlsx",
            data=buffer,
            file_name=f"Variasi_Penugasan_{quarter}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def variation_page():
    supabase = get_db_connection()

    st.title("Parameter 2 — Variasi Penugasan (30%)")
    st.caption(
        f"Variasi Score = (n Frekuensi Expert / {TOTAL_BOBOT_ASSIGNMENT}) x 30% — "
        "n Frekuensi Expert adalah jumlah bobot dari KELOMPOK assignment resmi "
        "(Teaching, Expert Insight, Learning Content, Coaching/Mentoring, "
        "Penguji/Assessor) yang PERNAH dikerjakan expert, dihitung sekali per "
        "kelompok terlepas dari repetisinya. Catatan: Coaching (Coach) dan "
        "Mentoring (Mentor) tetap ditampilkan terpisah di tabel detail, tapi "
        "dihitung sebagai satu kelompok bobot (1.3) untuk skor."
    )

    options = ["Upload file", "From Data Base"]
    mode = st.pills("Data Resource", options, selection_mode="single", default="From Data Base")

    if mode == "Upload file":
        st.header("📁 Upload File")

        quarter_upload = st.selectbox("Quarter untuk data ini", ["Q1", "Q2", "Q3", "Q4"])

        uploaded_files = st.file_uploader(
            "Upload data (format Excel)", accept_multiple_files=True, type=["xls", "xlsx"]
        )
        if uploaded_files:
            st.session_state["variasi_combined_df"] = read_and_merge(uploaded_files, quarter_upload)
            st.session_state["variasi_quarter"] = quarter_upload
        combined_df = st.session_state.get("variasi_combined_df", pd.DataFrame())
        quarter = st.session_state.get("variasi_quarter", quarter_upload)
    else:
        combined_df = load_all_data("learning_hour")

    if combined_df.empty:
        st.info("Tidak terdapat data")
        return

    if mode == "From Data Base":
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        quarter = st.pills("Pilih Quarter", quarters, selection_mode="single", default="Q1")
        if "quarter" in combined_df.columns:
            combined_df = combined_df[combined_df["quarter"] == quarter]

    if combined_df.empty:
        st.info(f"Tidak ada data untuk {quarter}. Pilih quarter lain yang sesuai dengan data.")
        return

    required_cols = ["nik", "expert", "activities"]
    missing_cols = [c for c in required_cols if c not in combined_df.columns]
    if missing_cols:
        st.error(
            f"Kolom berikut tidak ditemukan: {missing_cols}. Pastikan file/tabel sesuai "
            "format 'LH Recog/Request' (sheet 'direct,coe,self')."
        )
        return

    summary, touched, unmapped_values = compute_variasi_score(combined_df)

    if unmapped_values:
        st.warning(
            "⚠️ Ada nilai di kolom 'activities' yang tidak dikenali (di luar kategori "
            f"resmi) dan diabaikan dari perhitungan: {', '.join(unmapped_values)}"
        )

    spacer_l, col1, col2, spacer_r = st.columns([1, 2, 2, 1])
    col1.metric("Total Expert", summary["expert"].nunique(), border=True)
    col2.metric("Total Baris Assignment", len(combined_df), border=True)

    st.subheader("📋 Assignment/Variasi yang Dikerjakan per Expert")
    st.caption(
        "Setiap baris = satu kejadian assignment. Expert diurutkan dari yang PALING "
        "BANYAK assignment ke yang paling sedikit; di dalam satu expert, kategori "
        "diurutkan sesuai urutan resmi (Teaching → Expert Insight → Learning Content "
        "→ Coaching → Mentoring → Penguji/Assessor). 'Jumlah Assignment (Jenis Ini)' = "
        "berapa kali expert mengerjakan kategori yang sama pada baris itu. 'Total "
        "Assignment Expert' = total seluruh assignment expert (semua jenis digabung). "
        "'Skor Variasi Expert' = skor akhir expert tersebut, diulang di tiap barisnya."
    )
    detail_display = build_individual_assignment_table(combined_df, summary)
    st.dataframe(detail_display, use_container_width=True, hide_index=True)

    kategori_counts = (
        touched.groupby("kategori")["expert"].nunique().reset_index(name="jumlah_expert")
    )

    col_pie, col_bar = st.columns(2)
    with col_pie:
        st.subheader("🥧 Proporsi Assignment/Variasi")
        pie_fig = px.pie(
            kategori_counts,
            names="kategori",
            values="jumlah_expert",
            hole=0.4,
        )
        pie_fig.update_layout(legend_title_text="Assignment/Variasi")
        st.plotly_chart(pie_fig, use_container_width=True)

    with col_bar:
        st.subheader("📊 Jumlah Expert per Assignment/Variasi")
        bar_fig = px.bar(
            kategori_counts.sort_values("jumlah_expert", ascending=False),
            x="kategori",
            y="jumlah_expert",
            text="jumlah_expert",
        )
        bar_fig.update_layout(
            xaxis_title="Assignment/Variasi", yaxis_title="Jumlah Expert"
        )
        st.plotly_chart(bar_fig, use_container_width=True)

    st.subheader("📊 Rekap Variasi Penugasan per Expert")
    summary_display = summary[
        ["nik", "expert", "jumlah_kategori_dikerjakan", "n_frekuensi_expert", "variasi_score"]
    ].rename(
        columns={
            "nik": "NIK",
            "expert": "Expert",
            "jumlah_kategori_dikerjakan": "Jumlah Kelompok Bobot",
            "n_frekuensi_expert": "n Frekuensi Expert",
            "variasi_score": "Variasi Score (dari 30)",
        }
    )
    st.dataframe(summary_display, use_container_width=True)

    st.download_button(
        "Download rekap CSV",
        data=summary_display.to_csv(index=False).encode("utf-8"),
        file_name="variasi_penugasan_summary.csv",
        mime="text/csv",
    )

    _render_excel_download(detail_display, summary_display, quarter)

    if st.button("💾 Simpan Variasi Score ke Database", key="btn_save_variasi"):
        try:
            df_save = summary[["nik", "expert", "variasi_score"]].copy()
            df_save["quarter"] = quarter

            inserted = 0
            updated = 0
            for _, row in df_save.iterrows():
                existing = (
                    supabase.table("calculated")
                    .select("id")
                    .eq("nik", int(row["nik"]))
                    .eq("expert", row["expert"])
                    .eq("quarter", row["quarter"])
                    .execute()
                )
                if existing.data:
                    supabase.table("calculated").update(
                        {"variation": float(row["variasi_score"])}
                    ).eq("nik", int(row["nik"])).eq("expert", row["expert"]).eq(
                        "quarter", row["quarter"]
                    ).execute()
                    updated += 1
                else:
                    supabase.table("calculated").insert(
                        {
                            "nik": int(row["nik"]),
                            "expert": row["expert"],
                            "quarter": row["quarter"],
                            "variation": float(row["variasi_score"]),
                        }
                    ).execute()
                    inserted += 1

            st.success(f"✅ {inserted} insert + {updated} update untuk {quarter} (Variasi Score)")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


if __name__ == "__main__":
    variation_page()