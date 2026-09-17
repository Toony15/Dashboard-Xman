
from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

def uploadLim1(combined_df, DestinationTable, supabase, upload):
    if upload == True:
        try:
            df = combined_df[["id", "Email", "Event", "Question", "Answer", "Expert", "Unit", "Quarter"]]
            data = df.to_dict(orient="records")
            total_rows = len(data)

            if total_rows == 0:
                st.warning("⚠️ Tidak ada data untuk diupload.")
            else:
                st.info(f"⏳ Mengupload {total_rows} baris ke tabel '{DestinationTable}'...")
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, row in enumerate(data, start=1):
                    try:
                        supabase.table(DestinationTable).insert(row).execute()
                    except Exception as e:
                        st.error(f"❌ Gagal upload baris ke-{i}: {e}")
                        continue

                    progress = int(i / total_rows * 100)
                    progress_bar.progress(progress)
                    status_text.text(f"📤 Upload progress: {i}/{total_rows} baris ({progress}%)")

                progress_bar.empty()
                status_text.text("✅ Upload selesai.")
                st.success(f"Berhasil upload {total_rows} baris ke tabel '{DestinationTable}'")
                st.dataframe(df)

        except Exception as e:
            st.error(f"❌ Gagal upload: {e}")

REQUIRED_COLUMNS = {"NIK", "Name", "Question", "Answer"}
PLACEHOLDER_VALUES = {"-", "", "nan", "none", "null"}

CLASS_COLOR = {
    "Underperform": "#E24B4A",
    "Cukup Bagus": "#EF9F27",
    "Excellent": "#1D9E75",
}

SCORE_CATEGORY_COLOR = {"Rendah": "#E24B4A", "Tinggi": "#1D9E75"}


@dataclass
class ExpertResult:
    name: str
    n_participants: int
    average_score: float
    question_scores: pd.DataFrame
    comments: pd.DataFrame
    participant_scores: pd.DataFrame
    participant_avg: pd.DataFrame
    raw: pd.DataFrame
    numeric_questions: list = field(default_factory=list)
    text_questions: list = field(default_factory=list)


def is_placeholder(value) -> bool:
    if pd.isna(value):
        return True
    return str(value).strip().lower() in PLACEHOLDER_VALUES


def detect_numeric_questions(df: pd.DataFrame) -> tuple[list, list]:
    numeric_qs, text_qs = [], []
    for question, group in df.groupby("Question"):
        answers = group["Answer"].dropna()
        answers = answers[~answers.astype(str).str.strip().str.lower().isin(PLACEHOLDER_VALUES)]
        if len(answers) == 0:
            text_qs.append(question)
            continue
        numeric_ok = pd.to_numeric(answers, errors="coerce").notna()
        ratio_numeric = numeric_ok.mean()
        if ratio_numeric >= 0.6:
            numeric_qs.append(question)
        else:
            text_qs.append(question)
    return numeric_qs, text_qs


def process_expert_sheet(expert_name: str, df: pd.DataFrame) -> ExpertResult:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Sheet '{expert_name}' tidak punya kolom wajib: {', '.join(sorted(missing))}"
        )

    numeric_qs, text_qs = detect_numeric_questions(df)

    numeric_df = df[df["Question"].isin(numeric_qs)].copy()
    numeric_df["AnswerNum"] = pd.to_numeric(numeric_df["Answer"], errors="coerce")
    numeric_df = numeric_df.dropna(subset=["AnswerNum"])

    # dengan hasil hitung manual di Excel.
    per_participant = numeric_df.groupby(["NIK", "Name"], dropna=False)["AnswerNum"].mean().reset_index()
    per_participant["Nilai100"] = per_participant["AnswerNum"] * 10

    overall_average = (
        round(per_participant["Nilai100"].mean(), 2) if len(per_participant) else 0.0
    )

    participant_avg = per_participant.rename(columns={"AnswerNum": "Nilai"})[
        ["NIK", "Name", "Nilai", "Nilai100"]
    ].copy()
    participant_avg["Nilai"] = participant_avg["Nilai"].round(2)
    participant_avg["Nilai100"] = participant_avg["Nilai100"].round(2)

    per_question = numeric_df.groupby("Question")["AnswerNum"].mean().reset_index()
    per_question["Nilai"] = (per_question["AnswerNum"] * 10).round(2)
    per_question = per_question[["Question", "Nilai"]]

    text_df = df[df["Question"].isin(text_qs)].copy()
    text_df = text_df[~text_df["Answer"].apply(is_placeholder)]
    comments = text_df[["NIK", "Name", "Question", "Answer"]].reset_index(drop=True)

    participant_scores = numeric_df[["NIK", "Name", "Question", "AnswerNum"]].rename(
        columns={"AnswerNum": "Nilai"}
    )
    participant_scores["Nilai100"] = (participant_scores["Nilai"] * 10).round(2)
    participant_scores = participant_scores.reset_index(drop=True)

    return ExpertResult(
        name=expert_name,
        n_participants=df[["NIK", "Name"]].drop_duplicates().shape[0],
        average_score=overall_average,
        question_scores=per_question,
        comments=comments,
        participant_scores=participant_scores,
        participant_avg=participant_avg,
        raw=df,
        numeric_questions=numeric_qs,
        text_questions=text_qs,
    )


def classify(score: float, low: float, high: float) -> str:
    if score < low:
        return "Underperform"
    if score < high:
        return "Cukup Bagus"
    return "Excellent"


def categorize_score(nilai: float, threshold: float = 8.0) -> str:
    return "Rendah" if nilai < threshold else "Tinggi"


def load_workbook(uploaded_file) -> dict[str, pd.DataFrame]:
    """
    Baca semua sheet di file Excel, kembalikan HANYA sheet yang formatnya cocok
    (punya kolom NIK, Name, Question, Answer). Kalau tidak ada satupun yang cocok,
    kembalikan dict kosong -> berarti file ini BUKAN format raw-per-expert.
    """
    xls = pd.ExcelFile(uploaded_file)
    sheets = {}
    for sheet_name in xls.sheet_names:
        df = xls.parse(sheet_name)
        if df.empty or not REQUIRED_COLUMNS.issubset(set(str(c).strip() for c in df.columns)):
            continue
        sheets[sheet_name] = df
    return sheets


def try_detect_multi_expert_sheets(uploaded_files) -> tuple[dict, list]:
    """
    Coba baca setiap file yang diupload sebagai format 'raw feedback per expert'.
    Return: (dict semua sheet expert valid yang ditemukan, list file yang TIDAK cocok format ini)
    """
    all_expert_sheets = {}
    remaining_files = []
    for f in uploaded_files:
        try:
            sheets = load_workbook(f)
        except Exception:
            sheets = {}
        if sheets:
            for sheet_name, df in sheets.items():
                key = sheet_name if len(uploaded_files) == 1 else f"{f.name} - {sheet_name}"
                all_expert_sheets[key] = df
        else:
            remaining_files.append(f)
    return all_expert_sheets, remaining_files


LIM1_COMBINED_COLUMNS = ["NIK", "Name", "Email", "Unit", "Expert", "Event", "Quarter", "Question", "Answer"]


def build_lim1_combined_df(sheets: dict[str, pd.DataFrame], event: str, quarter: str) -> pd.DataFrame:
    """
    Ubah dict {nama_expert: df_mentah} (hasil try_detect_multi_expert_sheets) menjadi
    satu DataFrame panjang (1 baris = 1 jawaban per peserta per pertanyaan), dengan
    kolom Event & Quarter ditempel dari input manual user saat upload (bukan dideteksi
    otomatis dari isi file, karena file mentah tidak selalu punya info ini).

    Kolom 'Unit' diambil dari kolom 'Division' pada file mentah kalau ada
    (di data Telkom, Division berisi nama unit/regional seperti
    'DIVISI TELKOM REGIONAL IV', yang secara konsep setara dengan 'Unit').

    Kalau sheets kosong, kembalikan DataFrame kosong dengan kolom yang sudah benar
    (supaya pd.concat() dengan hasil format lain tidak error).
    """
    if not sheets:
        return pd.DataFrame(columns=LIM1_COMBINED_COLUMNS)

    frames = []
    for expert_name, df in sheets.items():
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]

        subset = pd.DataFrame({
            "NIK": df["NIK"] if "NIK" in df.columns else None,
            "Name": df["Name"] if "Name" in df.columns else None,
            "Email": df["Email"] if "Email" in df.columns else None,
            "Unit": df["Division"] if "Division" in df.columns else "",
            "Expert": expert_name,
            "Event": event,
            "Quarter": quarter,
            "Question": df["Question"] if "Question" in df.columns else None,
            "Answer": df["Answer"] if "Answer" in df.columns else None,
        })
        frames.append(subset)

    combined = pd.concat(frames, ignore_index=True)
    return combined[LIM1_COMBINED_COLUMNS]


def compute_overall_question_scores(results: list[ExpertResult]) -> pd.DataFrame:
    """
    Gabungkan nilai per pertanyaan dari SEMUA expert yang berhasil diolah (mewakili
    1 event lengkap, bukan per-expert), dipakai untuk tabel 'Rata-rata Nilai per
    Pertanyaan (Seluruh Expert)' di tab Ringkasan. Mengikuti pola tabel referensi:
    kolom 'Pertanyaan' / 'Nilai All', ditutup baris 'TOTAL AVERAGE'.

    PENTING: baris 'TOTAL AVERAGE' di sini SENGAJA dibuat sama dengan
    compute_grand_average() (rata-rata dari SELURUH jawaban mentah), bukan
    rata-rata dari rata-rata per-pertanyaan. Ini memastikan 'TOTAL AVERAGE'
    (per-pertanyaan) selalu identik dengan 'Rata-rata Keseluruhan' (per-expert)
    yang ditampilkan di atasnya - sesuai logika bisnis: keduanya sama-sama
    merangkum satu event yang sama, jadi harus menghasilkan satu angka yang sama,
    bukan kebetulan mirip karena datanya seimbang.
    """
    if not results:
        return pd.DataFrame(columns=["Pertanyaan", "Nilai All"])

    all_scores = pd.concat(
        [r.participant_scores[["Question", "Nilai"]] for r in results], ignore_index=True
    )
    if all_scores.empty:
        return pd.DataFrame(columns=["Pertanyaan", "Nilai All"])

    per_question = all_scores.groupby("Question", as_index=False)["Nilai"].mean()
    per_question["Nilai All"] = (per_question["Nilai"] * 10).round(2)
    per_question = per_question.rename(columns={"Question": "Pertanyaan"})[["Pertanyaan", "Nilai All"]]


    total_average = compute_grand_average(results)
    total_row = pd.DataFrame([{"Pertanyaan": "TOTAL AVERAGE", "Nilai All": total_average}])
    return pd.concat([per_question, total_row], ignore_index=True)


def compute_grand_average(results: list[ExpertResult]) -> float:
    """
    Hitung rata-rata SEBENARNYA dari seluruh jawaban individual (semua expert
    digabung jadi satu), BUKAN rata-rata dari rata-rata per-expert.

    Kenapa ini penting: kalau 'Rata-rata Keseluruhan' dihitung sebagai
    mean(rata-rata expert A, rata-rata expert B, ...), hasilnya cuma akan cocok
    dengan 'TOTAL AVERAGE' di tabel per-pertanyaan kalau jumlah peserta tiap
    expert kebetulan sama. Begitu jumlah peserta antar expert berbeda jauh,
    dua metode itu bisa selisih cukup besar. Menggabungkan semua jawaban dulu
    baru dirata-rata (grand average) menghasilkan SATU angka yang konsisten,
    tidak peduli berapa pun jumlah peserta/pertanyaan tiap expert.
    """
    if not results:
        return 0.0
    all_nilai = pd.concat([r.participant_scores["Nilai100"] for r in results], ignore_index=True)
    if all_nilai.empty:
        return 0.0
    return round(all_nilai.mean(), 2)


def build_download_excel(
    results: list[ExpertResult], low: float, high: float, score_threshold: float = 8.0
) -> bytes:
    summary_rows = []
    question_rows = []
    comment_rows = []
    participant_rows = []

    for r in results:
        kelas = classify(r.average_score, low, high)
        summary_rows.append(
            {
                "Expert": r.name,
                "Jumlah Peserta": r.n_participants,
                "Rata-rata Nilai": r.average_score,
                "Klasifikasi": kelas,
            }
        )
        for _, row in r.question_scores.iterrows():
            question_rows.append(
                {"Expert": r.name, "Pertanyaan": row["Question"], "Nilai": row["Nilai"]}
            )
        for _, row in r.comments.iterrows():
            comment_rows.append(
                {
                    "Expert": r.name,
                    "NIK": row["NIK"],
                    "Nama Peserta": row["Name"],
                    "Pertanyaan": row["Question"],
                    "Jawaban": row["Answer"],
                }
            )
        for _, row in r.participant_scores.iterrows():
            participant_rows.append(
                {
                    "Expert": r.name,
                    "NIK": row["NIK"],
                    "Nama Peserta": row["Name"],
                    "Pertanyaan": row["Question"],
                    "Nilai": row["Nilai"],
                    "Nilai (skala 100)": row["Nilai100"],
                    "Kategori": categorize_score(row["Nilai"], score_threshold),
                }
            )

    summary_df = pd.DataFrame(summary_rows).sort_values("Rata-rata Nilai", ascending=False)
    question_df = pd.DataFrame(question_rows)
    comment_df = pd.DataFrame(comment_rows)
    participant_df = pd.DataFrame(participant_rows)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Ringkasan Expert", index=False)
        question_df.to_excel(writer, sheet_name="Nilai per Pertanyaan", index=False)
        participant_df.to_excel(writer, sheet_name="Nilai per Peserta", index=False)
        comment_df.to_excel(writer, sheet_name="Komentar Peserta", index=False)
    buffer.seek(0)
    return buffer.getvalue()

def render_expert_feedback_results(sheets: dict):
    """
    Menampilkan hasil analisis untuk format 'raw feedback per expert'.
    `sheets` = dict {nama_sheet_atau_file: DataFrame}, sudah hasil deteksi otomatis
    dari try_detect_multi_expert_sheets(), BUKAN dari file_uploader baru.
    """
    with st.expander("⚙️ Pengaturan threshold klasifikasi", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            low_th = st.number_input(
                "Batas Underperform → Cukup Bagus", value=86.0, step=1.0, key="fa_low_th"
            )
        with col2:
            high_th = st.number_input(
                "Batas Cukup Bagus → Excellent", value=90.0, step=1.0, key="fa_high_th"
            )
        with col3:
            score_th = st.number_input(
                "Batas nilai per jawaban (skala 0-10)", value=8.0, step=0.5, key="fa_score_th"
            )
        if low_th >= high_th:
            st.warning("Batas bawah harus lebih kecil dari batas atas.")

    results = []
    errors = []
    for expert_name, df in sheets.items():
        try:
            results.append(process_expert_sheet(expert_name, df))
        except Exception as e:
            errors.append(str(e))

    for err in errors:
        st.warning(err)

    if not results:
        st.error("Tidak ada data expert yang berhasil diolah.")
        return

    results.sort(key=lambda r: r.average_score, reverse=True)

    summary_df = pd.DataFrame(
        [
            {
                "Expert": r.name,
                "Jumlah Peserta": r.n_participants,
                "Rata-rata Nilai": r.average_score,
                "Klasifikasi": classify(r.average_score, low_th, high_th),
            }
            for r in results
        ]
    )

    tab_ringkasan, tab_detail, tab_data = st.tabs(
        ["Ringkasan", "Detail per Expert", "Data Mentah"]
    )

    with tab_ringkasan:
        col1, col2, col3 = st.columns(3)
        col1.metric("Jumlah Expert", len(results))
        col2.metric("Total Peserta (unik per sheet)", int(summary_df["Jumlah Peserta"].sum()))
        col3.metric("Rata-rata Keseluruhan", f"{compute_grand_average(results):.2f}")

        st.subheader("Tabel ringkasan")
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        c1, c2 = st.columns([2, 1])
        with c1:
            bar = px.bar(
                summary_df,
                x="Rata-rata Nilai",
                y="Expert",
                orientation="h",
                color="Klasifikasi",
                color_discrete_map=CLASS_COLOR,
                text="Rata-rata Nilai",
            )
            bar.update_layout(yaxis={"categoryorder": "total ascending"}, height=400)
            st.plotly_chart(bar, use_container_width=True)
        with c2:
            pie = px.pie(
                summary_df,
                names="Klasifikasi",
                color="Klasifikasi",
                color_discrete_map=CLASS_COLOR,
                hole=0.4,
            )
            pie.update_layout(height=400)
            st.plotly_chart(pie, use_container_width=True)

        download_bytes = build_download_excel(results, low_th, high_th, score_th)
        st.download_button(
            "Download hasil olahan (Excel)",
            data=download_bytes,
            file_name="Hasil_Olahan_Feedback_Expert.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with tab_detail:
        expert_choice = st.selectbox(
            "Pilih expert", [r.name for r in results], key="fa_expert_choice"
        )
        r = next(x for x in results if x.name == expert_choice)
        kelas = classify(r.average_score, low_th, high_th)

        c1, c2 = st.columns(2)
        c1.metric("Rata-rata nilai", f"{r.average_score:.2f}")
        c2.metric("Klasifikasi", kelas)

        st.subheader("Rata-rata nilai per pertanyaan")
        if len(r.question_scores):
            radar = go.Figure()
            radar.add_trace(
                go.Scatterpolar(
                    r=r.question_scores["Nilai"],
                    theta=r.question_scores["Question"],
                    fill="toself",
                    name=r.name,
                )
            )
            radar.update_layout(
                polar={"radialaxis": {"visible": True, "range": [0, 100]}},
                showlegend=False,
                height=420,
            )
            st.plotly_chart(radar, use_container_width=True)
            st.dataframe(r.question_scores, use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada pertanyaan rating (numerik) terdeteksi pada sheet ini.")

        st.subheader("Nilai per peserta")
        if len(r.participant_avg):
            avg_df = r.participant_avg.copy()
            avg_df["Kategori"] = avg_df["Nilai"].apply(lambda v: categorize_score(v, score_th))
            avg_df = avg_df.rename(
                columns={
                    "Name": "Nama Peserta",
                    "Nilai": "Rata-rata Nilai",
                    "Nilai100": "Rata-rata Nilai (skala 100)",
                }
            )

            counts = (
                avg_df["Kategori"].value_counts().reindex(["Rendah", "Tinggi"]).fillna(0).astype(int)
            )
            count_df = pd.DataFrame({"Kategori": counts.index, "Jumlah Peserta": counts.values})

            c1, c2 = st.columns([1, 2])
            with c1:
                m1, m2 = st.columns(2)
                m1.metric("Jumlah peserta menilai Rendah", int(counts["Rendah"]))
                m2.metric("Jumlah peserta menilai Tinggi", int(counts["Tinggi"]))
            with c2:
                cat_bar = px.bar(
                    count_df,
                    x="Kategori",
                    y="Jumlah Peserta",
                    color="Kategori",
                    color_discrete_map=SCORE_CATEGORY_COLOR,
                    text="Jumlah Peserta",
                )
                cat_bar.update_layout(height=220, showlegend=False)
                st.plotly_chart(cat_bar, use_container_width=True)

            st.caption(
                "Kategori di atas berdasarkan rata-rata nilai (skala 0-10) yang diberikan "
                f"masing-masing peserta ke expert ini: di bawah {score_th:g} = Rendah, "
                f"{score_th:g} ke atas = Tinggi."
            )
            st.dataframe(
                avg_df[
                    ["NIK", "Nama Peserta", "Rata-rata Nilai", "Rata-rata Nilai (skala 100)", "Kategori"]
                ],
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Lihat rincian nilai per jawaban (per pertanyaan)"):
                detail_df = r.participant_scores.copy()
                detail_df["Kategori"] = detail_df["Nilai"].apply(
                    lambda v: categorize_score(v, score_th)
                )
                detail_df = detail_df.rename(
                    columns={
                        "Name": "Nama Peserta",
                        "Question": "Pertanyaan",
                        "Nilai100": "Nilai (skala 100)",
                    }
                )
                st.dataframe(
                    detail_df[
                        ["NIK", "Nama Peserta", "Pertanyaan", "Nilai", "Nilai (skala 100)", "Kategori"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("Tidak ada data nilai individual pada sheet ini.")

        st.subheader("Jawaban teks / saran dari peserta")
        if len(r.comments):
            st.dataframe(
                r.comments.rename(
                    columns={"Name": "Nama Peserta", "Question": "Pertanyaan", "Answer": "Jawaban"}
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Tidak ada jawaban teks yang tercatat untuk expert ini.")

    with tab_data:
        expert_choice2 = st.selectbox(
            "Lihat data mentah expert", [r.name for r in results], key="fa_raw_select"
        )
        r2 = next(x for x in results if x.name == expert_choice2)
        st.caption(f"Pertanyaan rating terdeteksi: {', '.join(r2.numeric_questions) or '-'}")
        st.caption(f"Pertanyaan teks terdeteksi: {', '.join(r2.text_questions) or '-'}")
        st.dataframe(r2.raw, use_container_width=True)