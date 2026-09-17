import pandas as pd
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection


BOBOT_MAP = {
    "Coaching (Coach)": 1.3,
    "Mentoring (Mentor)": 1.3,
    "Expert Insight (Pembicara)": 1.4,
    "Teaching": 1.5,
    "Learning Content Designer/Developer": 1.4,
    "Penguji/Assessor": 1.3,
}

PERSENTASE_POIN_LH = 60  # persentase poin LH terhadap skor akhir (0-100)


def read_and_merge(files, quarter_upload):
    """
    Parser file raw 'LH Recog/Request' (sheet 'direct,coe,self').
    Dibutuhkan: nik, expert (dari 'name'), gender, variasi (dari 'activities'),
    learning_hour, month, year.
    """
    column_mapping = {
        "nik": "nik",
        "name": "expert",
        "gender": "gender",
        "activities": "variasi",
        "learning_hour": "learning_hour",
        "month": "month",
        "year": "year",
    }

    all_data = []
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


def compute_learning_hour_scores(df):
    """
    Hitung bobot, poin, dan skor Learning Hour per baris assignment, lalu
    tambahkan kolom 'final_lh' (total skor_lh per expert, diulang di tiap
    baris miliknya) dan urutkan baris dari expert dengan jumlah assignment
    PALING BANYAK ke PALING SEDIKIT.

    Return: (df dengan kolom tambahan & sudah terurut, list nilai 'variasi'
    yang tidak dikenali di BOBOT_MAP)
    """
    work = df.copy()
    work["bobot"] = work["variasi"].map(BOBOT_MAP)

    unmapped_variasi = sorted(
        work.loc[work["bobot"].isna() & work["variasi"].notna(), "variasi"]
        .astype(str)
        .unique()
        .tolist()
    )
    work["bobot"] = work["bobot"].fillna(1.0)

    work["poin_lh"] = work["learning_hour"] * work["bobot"]
    work["persentase_poin"] = PERSENTASE_POIN_LH
    work["skor_lh"] = work["poin_lh"] * (work["persentase_poin"] / 100)

    total_per_expert = (
        work.groupby(["nik", "expert"])
        .agg(jumlah_assignment=("skor_lh", "size"), final_lh=("skor_lh", "sum"))
        .reset_index()
    )
    work = work.merge(total_per_expert, on=["nik", "expert"], how="left")

    expert_order = (
        total_per_expert.sort_values("jumlah_assignment", ascending=False)
        .apply(lambda r: (r["nik"], r["expert"]), axis=1)
        .tolist()
    )
    work["_expert_key"] = pd.Categorical(
        list(zip(work["nik"], work["expert"])), categories=expert_order, ordered=True
    )
    work = work.sort_values("_expert_key").drop(columns="_expert_key").reset_index(drop=True)

    return work, unmapped_variasi


def build_rekap_table(df):
    """Rekap total Learning Hour Score per expert, diurutkan skor tertinggi dulu."""
    rekap = df.groupby(["nik", "expert"], as_index=False).agg(
        learning_hour=("learning_hour", "sum"),
        bobot=("bobot", "first"),
        poin_lh=("poin_lh", "sum"),
        skor_lh=("skor_lh", "sum"),
    )
    rekap["nik"] = rekap["nik"].astype(int)
    return rekap.sort_values("skor_lh", ascending=False).reset_index(drop=True)


def save_scores_to_db(supabase, rekap, quarter):
    """Upsert skor Learning Hour tiap expert ke tabel 'calculated'. Return jumlah baris."""
    upload_df = rekap[["nik", "expert", "skor_lh"]].rename(columns={"skor_lh": "learning_hour"})

    for _, row in upload_df.iterrows():
        supabase.table("calculated").upsert(
            {
                "nik": int(row["nik"]),
                "expert": row["expert"],
                "quarter": quarter,
                "learning_hour": float(row["learning_hour"]),
            },
            # PENTING: tanpa on_conflict, Supabase mendeteksi duplikat lewat kolom
            # 'id' (primary key). Karena 'id' tidak pernah kita kirim, tiap panggilan
            # upsert() dianggap INSERT baru, lalu gagal kalau kombinasi
            # (nik, expert, quarter) itu SUDAH ADA - melanggar UNIQUE constraint
            # 'calculated_nik_expert_quarter_key'. on_conflict di sini memberi tahu
            # Supabase: "anggap duplikat kalau (nik, expert, quarter) sama", supaya
            # baris yang sudah ada di-UPDATE, bukan gagal insert.
            on_conflict="nik,expert,quarter",
        ).execute()

    return len(upload_df)


def learningHour():
    supabase = get_db_connection()

    st.title("Learning Hours")
    mode = st.pills(
        "Data Resource", ["Upload file", "From Data Base"],
        selection_mode="single", default="From Data Base",
    )

    if mode == "Upload file":
        st.header("📁 Upload File")
        quarter_upload = st.selectbox("Quarter untuk data ini", ["Q1", "Q2", "Q3", "Q4"])
        uploaded_files = st.file_uploader(
            "Upload data (format Excel)", accept_multiple_files=True, type=["xls", "xlsx"]
        )
        if uploaded_files:
            st.session_state["combined_df"] = read_and_merge(uploaded_files, quarter_upload)
            st.session_state["lh_quarter"] = quarter_upload
        combined_df = st.session_state.get("combined_df", pd.DataFrame())
        quarter = st.session_state.get("lh_quarter", quarter_upload)
    else:
        combined_df = load_all_data("learning_hour")

    if combined_df.empty:
        st.info("Tidak terdapat data")
        return

    st.dataframe(combined_df)

    if mode == "From Data Base":
        quarter = st.pills(
            "Pilih Quarter", ["Q1", "Q2", "Q3", "Q4"], selection_mode="single", default="Q1"
        )
        if "quarter" in combined_df.columns:
            combined_df = combined_df[combined_df["quarter"] == quarter]

    if combined_df.empty:
        st.info(f"Tidak ada data untuk {quarter}. Pilih quarter lain yang sesuai dengan data.")
        return

    if "variasi" not in combined_df.columns:
        st.warning("Kolom 'variasi' tidak ditemukan")
        return

    combined_df, unmapped_variasi = compute_learning_hour_scores(combined_df)

    if unmapped_variasi:
        st.warning(
            "⚠️ Ada nilai di kolom 'variasi' yang tidak dikenali dan bobotnya di-default "
            f"ke 1.0: {', '.join(unmapped_variasi)}"
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Learning Hour", combined_df["learning_hour"].sum(), border=True)
    col2.metric(
        "Average Learning Hour",
        round(combined_df["learning_hour"].sum() / combined_df["expert"].nunique(), 2),
        border=True,
    )
    col3.metric("Total Expert", combined_df["expert"].nunique(), border=True)

    st.subheader("📋 Detail Perhitungan Learning Hour")
    st.caption(
        "Expert diurutkan dari yang PALING BANYAK assignment ke yang paling sedikit. "
        "'Final LH' = total seluruh 'skor_lh' milik expert tersebut (dari semua "
        "baris assignment-nya), diulang di tiap barisnya."
    )
    detail_display = combined_df[
        ["nik", "expert", "variasi", "learning_hour", "bobot", "poin_lh",
         "persentase_poin", "skor_lh", "final_lh"]
    ].rename(columns={"variasi": "Jenis Assignment/Penugasan", "final_lh": "Final LH"})
    detail_display["Final LH"] = detail_display["Final LH"].round(2)
    st.dataframe(detail_display, use_container_width=True, hide_index=True)

    rekap_lh = build_rekap_table(combined_df)

    st.subheader("📊 Rekap Learning Hour Score per Expert (0-100)")
    st.dataframe(
        rekap_lh[["nik", "expert", "learning_hour", "bobot", "skor_lh"]],
        use_container_width=True,
    )

    # === DOWNLOAD EXCEL ===
    if st.button("Download Hasil Learning Hour (Excel)", key="btn_download_lh"):
        detail_download = combined_df[
            ["nik", "expert", "quarter", "variasi", "learning_hour", "bobot",
             "poin_lh", "persentase_poin", "skor_lh", "final_lh"]
        ].copy()

        rekap_download = rekap_lh[["nik", "expert", "learning_hour", "bobot", "poin_lh", "skor_lh"]].copy()

        import io
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            detail_download.to_excel(writer, sheet_name="Detail", index=False)
            rekap_download.to_excel(writer, sheet_name="Rekap", index=False)

        buffer.seek(0)

        st.download_button(
            label="Download Learning_Hour.xlsx",
            data=buffer,
            file_name=f"Learning_Hour_{quarter}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if st.button("💾 Simpan Learning Hour Score ke Database", key="btn_save_lh"):
        try:
            count = save_scores_to_db(supabase, rekap_lh, quarter)
            st.success(f"✅ {count} data disimpan/diupdate untuk {quarter}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")


if __name__ == "__main__":
    learningHour()