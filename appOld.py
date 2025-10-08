import streamlit as st
import pandas as pd
from google import genai
import io

# --- 🎛️ Konfigurasi Sidebar Menu ---
st.sidebar.title("📁 Menu Utama")
menu = st.sidebar.radio(
    "Pilih Halaman:",
    ["Satisfaction", "Learning Hour", "Variation", "Compensation"]
)

# --- 📄 BAGIAN UTAMA SESUAI MENU ---
if menu == "Satisfaction":
    st.title("📊 Upload File")

    uploaded_files = st.file_uploader(
        "Upload data (format Excel)", 
        accept_multiple_files=True, 
        type=["xls", "xlsx"]
    )

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
            event, expert, unit = (parts + ["", "", ""])[:3]

            # Tambahkan kolom metadata
            df["Event"] = event
            df["Expert"] = expert
            df["Unit"] = unit
            all_data.append(df)

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            combined["Event"] = combined["Event"].fillna("").astype(str).str.strip()
            return combined
        else:
            return pd.DataFrame()

    # Simpan hasil upload ke session_state agar tidak hilang setelah interaksi
    if uploaded_files:
        st.session_state["combined_df"] = read_and_merge(uploaded_files)

    # Ambil data dari session_state
    combined_df = st.session_state.get("combined_df", pd.DataFrame())

    if combined_df.empty:
        st.info("Silakan unggah satu atau beberapa file Excel terlebih dahulu.")
    else:
        st.success(f"✅ Data berhasil digabungkan ({len(combined_df)} baris total)")
        st.dataframe(combined_df)

        st.markdown("---")
        st.subheader("🎯 Pilih Event untuk Ditampilkan")

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

            st.markdown(f"### 📋 Data untuk Event: `{selected_event}` ({len(filtered_df)} baris)")
            st.dataframe(filtered_df)
            
            # --- 🔍 Rekap Umum Sebelum Dataframe Detail ---
            qid_col = "Question ID"
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

                st.markdown("## 📊 Rekap Umum")

                # --- Table 1: Rata-rata per Expert ---
                if not numeric_df.empty:
                    rekap_expert = numeric_df.groupby(expert_col, as_index=False)[answer_col].mean()
                    rekap_expert["AVERAGE"] = rekap_expert[answer_col] * 10
                    rekap_expert = rekap_expert.rename(columns={expert_col: "NAMA"})[["NAMA", "AVERAGE"]]

                    st.markdown("### 👨‍🏫 Rata-rata Nilai per Expert")
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

                    st.markdown("### 🧩 Rata-rata Nilai per Pertanyaan (Semua Expert)")
                    st.dataframe(rekap_question, use_container_width=True)
                else:
                    st.info("Tidak ada data numerik untuk menghitung rata-rata per pertanyaan.")

                st.markdown("---")
            
            #--- Tampilkan data per Expert ---
            st.markdown("## 👨‍🏫 Rekap per Expert")

            experts = sorted(filtered_df["Expert"].unique())

            if not experts:
                st.info("Tidak ada data Expert dalam event ini.")
            else:
                selected_expert = st.selectbox(
                    "Pilih Expert untuk ditampilkan:",
                    options=experts,
                    index=0,
                    help="Pilih salah satu expert untuk melihat rekap datanya"
                )

                expert_df = filtered_df[filtered_df["Expert"] == selected_expert]

                st.markdown(f"### 🔹 Expert: **{selected_expert}**")

                # Pisahkan jawaban numerik dan deskriptif
                numeric_df = expert_df[pd.to_numeric(expert_df["Answer"], errors="coerce").notna()].copy()
                text_df = expert_df[pd.to_numeric(expert_df["Answer"], errors="coerce").isna()].copy()

                # --- Table 1: Rekap Nilai Numerik ---
                if not numeric_df.empty:
                    numeric_df["Answer"] = numeric_df["Answer"].astype(float)
                    rekap_nilai = (
                        numeric_df.groupby(["Question"], as_index=False)["Answer"]
                        .mean()
                    )
                    rekap_nilai["Nilai (x10)"] = rekap_nilai["Answer"] * 10
                    rekap_nilai = rekap_nilai[["Question", "Nilai (x10)"]]

                    st.markdown("##### 📊 Rekap Nilai (Pertanyaan Numerik)")
                    st.dataframe(rekap_nilai, use_container_width=True)
                else:
                    st.info("Tidak ada data numerik untuk expert ini.")

                # --- Table 2: Rekap Jawaban Deskriptif ---
                if not text_df.empty:
                    text_df = text_df.reset_index(drop=True)
                    text_df.index += 1
                    rekap_teks = text_df[["Answer", "Objective"]].rename_axis("No").reset_index()

                    st.markdown("##### 💬 Rekap Jawaban Deskriptif")
                    st.dataframe(rekap_teks, use_container_width=True)
                else:
                    st.info("Tidak ada jawaban deskriptif untuk expert ini.")
                
                        # --- 📈 RESUME SECTION ---
            st.markdown("---")
            st.header("📊 Resume Keseluruhan")

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

            # --- Grafik 1: Jumlah Pelatihan per Unit ---
            st.subheader("📊 Grafik Jumlah Pelatihan per Unit")

            unit_count = resume_df.groupby("Unit", as_index=False)["Event"].nunique()
            unit_count = unit_count.rename(columns={"Event": "Jumlah Pelatihan"})

            st.bar_chart(event_count.set_index("unit")["jumlah_event"])
            # st.bar_chart(unit_count.set_index("Unit")["Jumlah Pelatihan"])

            st.markdown("#### 📋 Tabel Jumlah Pelatihan per Unit")
            # st.dataframe(unit_count, use_container_width=True)
            st.dataframe(event_count, use_container_width=True)

            # --- Table 1: Nilai Rata-rata per Event ---
            st.subheader("🧾 Table 1: Nilai Rata-rata per Event")

            if resume_df["is_numeric"].any():
                table1 = (
                    resume_df[resume_df["is_numeric"]]
                    .groupby(["Event", "Unit"], as_index=False)["Answer_Numeric"]
                    .mean()
                )
                table1["NILAI AVERAGE"] = table1["Answer_Numeric"] * 10
                table1 = table1.reset_index().rename(
                    columns={
                        "index": "NO",
                        "Event": "NAMA EVENT",
                        "Unit": "UNIT"
                    }
                )[["NO", "NAMA EVENT", "UNIT", "NILAI AVERAGE"]]

                st.dataframe(table1, use_container_width=True)
            else:
                st.info("Tidak ada data numerik untuk menghitung rata-rata per event.")

            # --- Table 2: Nilai Rata-rata per Pertanyaan ---
            st.subheader("🧩 Table 2: Nilai Rata-rata per Pertanyaan")

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

            # --- Table 3: Rekap Pertanyaan Deskriptif per Event ---
            st.subheader("💬 Table 3: Rekap Pertanyaan Deskriptif per Event")

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

                st.dataframe(table3, use_container_width=True)

                # Debug info (bisa dihapus nanti)
                st.write("📦 Jumlah Nilai Pertanyaan yang Disimpan:", len(nilai_pertanyaan_list))
            else:
                st.info("Tidak ada data deskriptif untuk ditampilkan pada tabel ini.")
            
            # --- Simpan jawaban deskriptif dari seluruh event ---
            text_df_all = combined_df[pd.to_numeric(combined_df["Answer"], errors="coerce").isna()].copy()
            nilai_pertanyaan_list = text_df_all["Answer"].dropna().astype(str).tolist()

            st.markdown("### 🧠 Resume Otomatis (dari Jawaban Deskriptif)")

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
                    Analisis dan ringkaslah hasil berikut secara profesional dan terstruktur.
                    Data berikut berisi hasil evaluasi atau penilaian individu/kelompok.

                    Tugas Anda:
                    1. Sajikan ringkasan umum dari hasil tersebut.
                    2. Jelaskan kelebihan utama (aspek positif yang menonjol).
                    3. Jelaskan kekurangan atau area yang masih perlu diperbaiki.
                    4. Sebutkan rekomendasi perbaikan atau pengembangan ke depannya.
                    5. Jika memungkinkan, berikan penilaian keseluruhan dalam satu paragraf akhir.

                    Gunakan gaya bahasa profesional dan ringkas seperti laporan manajerial.
                    Jangan menyalin mentah-mentah isi teks, tetapi buatlah sintesis berdasarkan pemahaman Anda.

                    Berikut data yang harus dianalisis:
                    --------------------
                    {data_text}
                    --------------------
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

                if st.button("💾 Download Semua Data dalam Excel"):
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                        # Sheet 1 - Data Gabungan
                        combined_df.to_excel(writer, index=False, sheet_name="Data Gabungan")

                        # Sheet 2 - Data Filter Event
                        if not filtered_df.empty:
                            filtered_df.to_excel(writer, index=False, sheet_name=f"Event_{selected_event[:25]}")

                        # Sheet 3 - Rekap per Expert
                        if 'rekap_expert' in locals():
                            rekap_expert.to_excel(writer, index=False, sheet_name="Rekap Expert")

                        # Sheet 4 - Rekap per Pertanyaan
                        if 'rekap_question' in locals():
                            rekap_question.to_excel(writer, index=False, sheet_name="Rekap Pertanyaan")

                        # Sheet 5 - Rekap per Expert (Detail)
                        if 'rekap_nilai' in locals():
                            rekap_nilai.to_excel(writer, index=False, sheet_name=f"Nilai_{selected_expert[:20]}")

                        # Sheet 6 - Jawaban Deskriptif
                        if 'rekap_teks' in locals():
                            rekap_teks.to_excel(writer, index=False, sheet_name=f"Deskripsi_{selected_expert[:20]}")

                        # Sheet 7 - Grafik Jumlah Pelatihan per Unit
                        if 'unit_count' in locals():
                            unit_count.to_excel(writer, index=False, sheet_name="Grafik Pelatihan per Unit")

                        # Sheet 8 - Rata-rata per Event
                        if 'table1' in locals():
                            table1.to_excel(writer, index=False, sheet_name="Rata-rata Event")

                        # Sheet 9 - Rata-rata per Pertanyaan
                        if 'table2' in locals():
                            table2.to_excel(writer, index=False, sheet_name="Rata-rata Pertanyaan")

                        # Sheet 10 - Rekap Pertanyaan Deskriptif
                        if 'table3' in locals():
                            table3.to_excel(writer, index=False, sheet_name="Deskriptif per Event")

                        # Sheet 11 - Resume dari Gemini
                        if 'response' in locals() and hasattr(response, 'text'):
                            pd.DataFrame({
                                ["Resume Otomatis dari Gemini"]: [response.text]
                            }).to_excel(writer, index=False, sheet_name="Resume Gemini")

                        writer.close()

                    # Buat tombol download
                    st.download_button(
                        label="⬇️ Simpan File Excel",
                        data=output.getvalue(),
                        file_name=f"Rekap_Evaluasi_{selected_event}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

elif menu == "Learning Hour":
    st.title("⏱️ Learning Hour")
    st.info("Halaman ini masih dalam pengembangan. Nantinya berisi analisis learning hour per unit/event.")

elif menu == "Variation":
    st.title("📈 Variation Analysis")
    st.info("Halaman ini akan menampilkan variasi nilai antar event atau antar expert.")
elif menu == "Compensation":
    st.title("💰 Compensation Calculation")
    st.info("Halaman ini akan Menghitung kompensasi yang diterima expert.")