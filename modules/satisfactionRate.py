import streamlit as st
import pandas as pd
import io
from dbConfig import get_db_connection
from google import genai
from dataManager import load_all_data

def satisfaction_page():
    supabase = get_db_connection()
    def read_and_merge(files):
        all_data = []
        for uploaded_file in files:
            try:
                df = pd.read_excel(uploaded_file)
            except Exception as e:
                st.error(f"Gagal membaca file {uploaded_file.name}: {e}")
                continue
            # Ambil nama file tanpa ekstensi
            file_name = uploaded_file.name.rsplit(".", 1)[0]
            parts = file_name.split("_")
            event, expert, unit,quarter = (parts + ["", "", "", ""])[:4]

            # Tambahkan kolom metadata
            df["Event"] = event
            df["Expert"] = expert
            df["Unit"] = unit
            df["Quarter"] = quarter
            all_data.append(df)

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined["Event"] = combined["Event"].fillna("").astype(str).str.strip()
            return combined
        else:
            return pd.DataFrame()
    
    st.title("Learning Impact 1 (LIM 1)")  
    options = ["Upload file","From Data Base"]
    mode = st.pills("Data Resource", options, selection_mode="single", default="Upload file")
    if mode == "Upload file":   
        st.header("Upload File")

        uploaded_files = st.file_uploader(
            "Upload data (format Excel)", 
            accept_multiple_files=True, 
            type=["xls", "xlsx"]
        )
        # Simpan hasil upload ke session_state agar tidak hilang setelah interaksi
        if uploaded_files:
            st.session_state["combined_df"] = read_and_merge(uploaded_files)
        # Ambil data dari session_state
        combined_df = st.session_state.get("combined_df", pd.DataFrame())
    elif mode == "From Data Base":
        viewTable="learningImpact1"
        combined_df = load_all_data(viewTable)
    if combined_df.empty:
        st.info("Tidak terdapat data")
    else:
        options = ["Q1", "Q2", "Q3", "Q4"]
        default_selection = options
        selectedQuarter = st.pills("Select Quarter", options, selection_mode="multi", default=default_selection)
        
        combined_df = combined_df[combined_df["Quarter"].isin(selectedQuarter)]
        # st.success(f"✅ Data berhasil digabungkan ({len(combined_df)} baris total)")
        st.dataframe(combined_df)
        st.markdown("""
                <style>
                div[data-baseweb="tab-list"] {
                    justify-content: space-between; /* Membagi tab secara merata */
                    width: 100%;
                }
                button[data-baseweb="tab"] {
                    flex: 1; /* Membuat tiap tab memiliki lebar sama */
                    max-width: 100%;
                }
                </style>
            """, unsafe_allow_html=True)
        tab1, tab2= st.tabs(["Overview", "Detail"])
        
        # ==========================================================
        # DETAIL
        # ==========================================================
        
        with tab2:
            st.subheader("Pilih Event untuk Ditampilkan")

            # Ambil daftar event unik
            unique_events = sorted([e for e in combined_df["Event"].unique() if e.strip() != ""])

            if not unique_events:
                st.warning("Tidak ditemukan nama Event. Pastikan nama file memiliki format 'event_expert_unit'.")
            else:
                # Selectbox untuk memilih satu event
                selected_event = st.selectbox(
                    "Pilih Event:",
                    options=unique_events,
                    index=0,
                    help="Pilih satu event untuk menampilkan datanya"
                )

                # Filter dataframe sesuai event yang dipilih
                filtered_df = combined_df[combined_df["Event"] == selected_event]

                st.markdown(f"### Data untuk Event: `{selected_event}` ({len(filtered_df)} baris)")
                st.dataframe(filtered_df)
                
                # --- 🔍 Rekap Umum Sebelum Dataframe Detail ---
                qtext_col = "Question"
                answer_col = "Answer"
                expert_col = "Expert"

                # Pastikan kolom ada
                if not all(col in filtered_df.columns for col in [qtext_col, answer_col, expert_col]):
                    st.warning("Beberapa kolom yang dibutuhkan tidak ditemukan (Pastikan ada kolom Question ID, Question, Answer, dan Expert).")
                else:
                    # Bersihkan nilai numeric
                    temp_df = filtered_df.copy()
                    temp_df[answer_col] = (
                        temp_df[answer_col]
                        .astype(str)
                        .str.replace(",", ".")
                        .str.replace(r"\s+", "", regex=True)
                    )

                    # Deteksi numeric
                    temp_df["is_numeric"] = pd.to_numeric(temp_df[answer_col], errors="coerce").notna()
                    numeric_df = temp_df[temp_df["is_numeric"]].copy()
                    numeric_df[answer_col] = pd.to_numeric(numeric_df[answer_col], errors="coerce")

                    st.markdown("## Rekap Umum")

                    # --- Table 1: Rata-rata per Expert ---
                    if not numeric_df.empty:
                        rekap_expert = numeric_df.groupby(expert_col, as_index=False)[answer_col].mean()
                        rekap_expert["AVERAGE"] = rekap_expert[answer_col] * 10
                        rekap_expert = rekap_expert.rename(columns={expert_col: "NAMA"})[["NAMA", "AVERAGE"]]

                        st.markdown("### Rata-rata Nilai per Expert")
                        st.dataframe(rekap_expert, use_container_width=True)
                    else:
                        st.info("Tidak ada data numerik untuk menghitung rata-rata per expert.")

                    # --- Table 2: Rata-rata per Pertanyaan (semua expert digabung) ---
                    if not numeric_df.empty:
                        rekap_question = numeric_df.groupby(qtext_col, as_index=False)[answer_col].mean()
                        rekap_question["NILAI ALL"] = rekap_question[answer_col] * 10
                        rekap_question = rekap_question.rename(columns={qtext_col: "PERTANYAAN UBPP STRUKTUR"})[
                            ["PERTANYAAN UBPP STRUKTUR", "NILAI ALL"]
                        ]

                        st.markdown("### Rata-rata Nilai per Pertanyaan (Semua Expert)")
                        st.dataframe(rekap_question, use_container_width=True)
                    else:
                        st.info("Tidak ada data numerik untuk menghitung rata-rata per pertanyaan.")

                    st.markdown("---")
                
                #--- Tampilkan data per Expert ---
                st.markdown("## Rekap per Expert")
                # --- Table 3: Rekap skor expert seluruh event ---
                st.subheader("Table 3: Rekap Skor Expert seluruh event")
                # ===== 🧠 FILTER EXPERT =====
                experts = sorted(filtered_df["Expert"].dropna().unique())
                # 🔹 Checkbox untuk memilih semua expert
                select_all = st.checkbox("Pilih Semua Expert")

                # 🔹 Jika dicentang, semua expert otomatis dipilih
                if select_all:
                    selected_experts = st.multiselect("👤 Pilih Expert", options=experts, default=experts)
                else:
                    selected_experts = st.multiselect("👤 Pilih Expert", options=experts, default=experts[:1])                

                # Konversi kolom Answer menjadi numeric jika memungkinkan
                combined_df["Answer_Numeric"] = pd.to_numeric(combined_df["Answer"], errors="coerce")
                # Jika tidak ada expert dipilih, tampilkan peringatan
                if not selected_experts:
                    st.warning("⚠️ Silakan pilih minimal satu expert untuk ditampilkan.")
                else:
                    # Loop untuk setiap expert yang dipilih
                    for expert in selected_experts:
                        st.markdown(f"### 👤 Expert: **{expert}**")

                        # Filter berdasarkan expert
                        filtered_df = combined_df[combined_df["Expert"] == expert].copy()
                        numeric_df = filtered_df.dropna(subset=["Answer_Numeric"]).copy()

                        # Hitung rata-rata nilai per pertanyaan
                        avg_per_question = (
                            numeric_df.groupby("Question")["Answer_Numeric"]
                            .mean()
                            .reset_index()
                            .rename(columns={"Answer_Numeric": "Average_Score"})
                        )

                        # Kalikan dengan 10
                        avg_per_question["Average_Score"] = avg_per_question["Average_Score"] * 10

                        # ========== CONTAINER 1 (Per Expert) ==========
                        with st.container():
                            sec1, sec2 = st.columns([2, 1])

                            # 📊 Tabel rata-rata per pertanyaan
                            with sec1:
                                st.subheader("📊 Rata-rata Nilai per Pertanyaan (Numeric)")
                                st.dataframe(avg_per_question, use_container_width=True)

                            # 🎯 Scorecard rata-rata keseluruhan
                            overall_avg = avg_per_question["Average_Score"].mean()
                            with sec2:
                                st.empty()
                                st.markdown(
                                    f"""
                                    <div style='text-align: center; padding: 20px; border-radius: 10px; background-color: #1f2937;'>
                                        <h3 style='color: white;'>🎯 Rata-rata Skor Keseluruhan</h3>
                                        <h1 style='color: #4CAF50;'>{overall_avg:.2f}</h1>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                        # Tambahkan garis pemisah antar expert
                        st.markdown("---")
            # =============================================================
            # OVERVIEW
            # =============================================================
            
            with tab1:        
                # --- 📈 RESUME SECTION ---
                st.markdown(
                    """
                    <h1 style='text-align: center;'>Overview</h1>
                    """,
                    unsafe_allow_html=True
                )

                # --- Persiapan Data ---
                resume_df = combined_df.copy()
                resume_df["Answer_Clean"] = (
                    resume_df["Answer"].astype(str)
                    .str.replace(",", ".")
                    .str.replace(r"\s+", "", regex=True)
                )
                resume_df["is_numeric"] = pd.to_numeric(resume_df["Answer_Clean"], errors="coerce").notna()
                resume_df["Answer_Numeric"] = pd.to_numeric(resume_df["Answer_Clean"], errors="coerce")
                grafik_df = combined_df[["Event", "Unit"]].copy()
                event_count = grafik_df.groupby("Unit")["Event"].nunique().reset_index()
                event_count.columns = ["unit", "jumlah_event"]
                st.markdown(
                    """
                    <h2 style='text-align: center;'>Jumlah Pelatihan per Unit</h2>
                    """,
                    unsafe_allow_html=True
                )
                colA1, colA2 = st.columns(2)
                with colA1:
                # --- Grafik 1: Jumlah Pelatihan per Unit ---
                    unit_count = resume_df.groupby("Unit", as_index=False)["Event"].nunique()
                    unit_count = unit_count.rename(columns={"Event": "Jumlah Pelatihan"})

                    st.bar_chart(event_count.set_index("unit")["jumlah_event"])
                    # st.bar_chart(unit_count.set_index("Unit")["Jumlah Pelatihan"])
                with colA2:
                    # st.dataframe(unit_count, use_container_width=True)
                    st.dataframe(event_count, use_container_width=True)
                colB1, colB2 = st.columns(2)
                with colB1:
                    # --- Table 1: Nilai Rata-rata per Event ---
                    st.subheader("🧾Nilai Rata-rata per Event")

                    if resume_df["is_numeric"].any():
                        table1 = (
                            resume_df[resume_df["is_numeric"]]
                            .groupby(["Event", "Unit"], as_index=False)["Answer_Numeric"]
                            .mean()
                        )
                        table1["NILAI AVERAGE"] = table1["Answer_Numeric"] * 10
                        table1 = table1.reset_index().rename(
                            columns={
                                "Event": "NAMA EVENT",
                                "Unit": "UNIT"
                            }
                        )[["NAMA EVENT", "UNIT", "NILAI AVERAGE"]]

                        st.dataframe(table1, use_container_width=True)
                    else:
                        st.info("Tidak ada data numerik untuk menghitung rata-rata per event.")
                with colB2:
                    # --- Table 2: Nilai Rata-rata per Pertanyaan ---
                    st.subheader("🧩Nilai Rata-rata per Pertanyaan")

                    if resume_df["is_numeric"].any():
                        table2 = (
                            resume_df[resume_df["is_numeric"]]
                            .groupby("Question", as_index=False)["Answer_Numeric"]
                            .mean()
                        )
                        table2["NILAI AVERAGE PERTANYAAN"] = table2["Answer_Numeric"] * 10
                        table2 = table2.reset_index().rename(
                            columns={
                                "index": "NO",
                                "Question": "PERTANYAAN UBPP"
                            }
                        )[["NO", "PERTANYAAN UBPP", "NILAI AVERAGE PERTANYAAN"]]

                        st.dataframe(table2, use_container_width=True)
                    else:
                        st.info("Tidak ada data numerik untuk menghitung rata-rata per pertanyaan.")

                # --- Table 3: Rekap skor expert seluruh event ---
                st.subheader("Table 3: Rekap Skor Expert seluruh event")
                numeric_df = resume_df[resume_df["is_numeric"]].copy()
                # Hitung rata-rata skor per expert
                avg_score_per_expert = (
                    numeric_df.groupby("Expert")["Answer_Numeric"]
                    .mean()
                    .reset_index()
                    .rename(columns={"Answer_Numeric": "Average_Score"})
                )


                # Opsional: bulatkan dua angka di belakang koma
                avg_score_per_expert["Average_Score"] = avg_score_per_expert["Average_Score"].round(3) * 10

                # Tampilkan hasil
                st.dataframe(avg_score_per_expert)

                # ===== 2️⃣ TABLE NON-NUMERIC =====
                non_numeric_df = combined_df[combined_df["Answer_Numeric"].isna()].copy()

                st.subheader("Rekap Jawaban Non-Numeric")
                st.dataframe(non_numeric_df, use_container_width=True)
                
                
                
                # --- Table 4: Rekap Pertanyaan Deskriptif per Event ---
                # st.subheader("Table 4: Rekap Pertanyaan Deskriptif per Event")

                text_df = resume_df[~resume_df["is_numeric"]].copy()
                if not text_df.empty:
                    table3 = text_df.reset_index().rename(
                        columns={
                            "index": "NO",
                            "Event": "NAMA EVENT",
                            "Question": "PERTANYAAN UBPP",
                            "Answer": "NILAI PERTANYAAN"
                        }
                    )[["NO", "NAMA EVENT", "PERTANYAAN UBPP", "NILAI PERTANYAAN"]]

                    # Simpan seluruh isi kolom NILAI PERTANYAAN ke variabel Python
                    nilai_pertanyaan_list = table3["NILAI PERTANYAAN"].tolist()

                    # st.dataframe(table3, use_container_width=True)

                    # Debug info (bisa dihapus nanti)
                    st.write("📦 Jumlah Nilai Pertanyaan yang Disimpan:", len(nilai_pertanyaan_list))
                else:
                    st.info("Tidak ada data deskriptif untuk ditampilkan pada tabel ini.")
                
                # --- Simpan jawaban deskriptif dari seluruh event ---
                text_df_all = combined_df[pd.to_numeric(combined_df["Answer"], errors="coerce").isna()].copy()
                nilai_pertanyaan_list = text_df_all["Answer"].dropna().astype(str).tolist()

                st.markdown("### Resume Otomatis (dari Jawaban Deskriptif)")

                st.write(f"Jumlah total jawaban deskriptif: {len(nilai_pertanyaan_list)}")

                if st.button("🔍 Buat Resume dengan Gemini API"):
                    if not nilai_pertanyaan_list:
                        st.warning("Tidak ada data teks untuk diringkas.")
                    else:
                        st.info("⏳ Mengirim data ke Gemini API untuk membuat ringkasan...")
                        # Simpan dulu ke session_state agar bisa diakses nanti
                        st.session_state["nilai_pertanyaan_list"] = nilai_pertanyaan_list
                        st.success("✅ Data berhasil disiapkan untuk dikirim ke Gemini API.")
                    # konfigurasi
                    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

                    if "nilai_pertanyaan_list" in st.session_state:
                        data_text = "\n".join(st.session_state["nilai_pertanyaan_list"])
                        prompt = f"""
                        Lakukan analisis data berikut dengan mengikuti instruksi proses secara ketat dan berurutan. 
                        Anda harus mematuhi seluruh langkah analisis, struktur output, dan gaya penulisan di bawah ini.

                        ======================
                        PROSES ANALISIS DATA
                        ======================

                        1. IDENTIFIKASI INTI INFORMASI
                        - Baca seluruh data dan temukan pola umum: tema, kecenderungan, dan fokus umpan balik.
                        - Kelompokkan isi ke dalam dua kategori besar: (a) aspek positif, (b) area perbaikan.

                        2. EKSTRAKSI INSIGHT
                        - Dari kategori positif, ambil 5 poin paling kuat yang benar-benar mewakili kekuatan utama.
                        - Dari kategori perbaikan, ambil 4 poin paling relevan untuk pengembangan.
                        - Sintesis insight: tidak boleh menyalin teks mentah, tetapi mengolahnya menjadi kalimat analitis.

                        3. PENILAIAN KRITIS
                        - Tinjau konsistensi antar poin dan pastikan masing-masing adalah temuan unik, bukan duplikasi.
                        - Susun insight sehingga mengalir dari yang paling fundamental ke yang bersifat teknis.

                        4. FORMULASI OUTPUT
                        - Hasil akhir wajib mengikuti format berikut:

                        ======================
                        FORMAT OUTPUT WAJIB
                        ======================

                        Judul 1: **Apresiasi**
                        Tampilkan minimal 5 poin bernomor.
                        Setiap poin harus memenuhi format:
                        - Dimulai dengan frasa kunci yang ditebalkan (**…**) sebagai highlight insight.
                        - Dilanjutkan 1–2 kalimat evaluatif yang ringkas, profesional, dan langsung ke inti.
                        - Maksimal 100 kata per poin.

                        Judul 2: **Saran**
                        Tampilkan minimal 5 poin bernomor.
                        Setiap poin menggunakan format yang sama:
                        - Frasa kunci ditebalkan (**…**).
                        - Diikuti penjelasan 1–2 kalimat yang bersifat korektif atau pengembangan.

                        ======================
                        GAYA PENULISAN
                        ======================
                        - Gunakan bahasa formal, manajerial, objektif, dan mudah dipahami.
                        - Tidak menggunakan kata yang bertele-tele.
                        - Fokus pada insight, bukan deskripsi ulang.
                        - Hindari jargon teknis berlebihan.
                        - Panjang keseluruhan harus padat namun komprehensif.

                        ======================
                        DATA YANG DIANALISIS
                        ======================
                        {data_text}

                        """

                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=prompt
                        )

                        st.markdown("### 📝 Resume dari Gemini")
                        st.write(response.text)
                    else:
                        st.warning("❗ Tidak ada data nilai_pertanyaan_list yang tersimpan. Pastikan Anda sudah menjalankan bagian Resume sebelumnya.")
                    
                    # --- 📦 BAGIAN DOWNLOAD EXCEL ---
                    st.markdown("---")
                    st.header("📥 Download Semua Data")
                    output = None
                    
                    # Buat tombol download
                    try:
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                                # Sheet 1 - Data Gabungan
                                combined_df.to_excel(writer, index=False, sheet_name="Data Gabungan")

                                # Sheet 2 - Data Event
                                if not event_count.empty:
                                    event_count.to_excel(writer, index=False, sheet_name=f"Event")

                                # Sheet 3 - Rekap per Expert
                                if 'avg_score_per_expert' in locals():
                                    avg_score_per_expert.to_excel(writer, index=False, sheet_name="Rekap Expert")
                                
                                if 'table1' in locals():
                                    table1.to_excel(writer, index=False, sheet_name="Rata-rata Event")

                                # Sheet 9 - Rata-rata per Pertanyaan
                                if 'table2' in locals():
                                    table2.to_excel(writer, index=False, sheet_name="Rata-rata Pertanyaan")

                                # Sheet 10 - Rekap Pertanyaan Deskriptif
                                if 'table3' in locals():
                                    table3.to_excel(writer, index=False, sheet_name="Deskriptif per Event")

                                writer.close()
                                st.download_button(
                                    label="⬇️ Simpan File Excel",
                                    data=output.getvalue(),
                                    file_name=f"Rekap_Evaluasi_{selectedQuarter}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    except Exception as e:
                        st.error(f"🚨 Terjadi kesalahan saat membuat file Excel: {e}")