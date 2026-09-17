import pandas as pd
import plotly.express as px
import streamlit as st
from dataManager import load_all_data
from dbConfig import get_db_connection


experLevel_PERSEN = 10
def expertLevel():
    supabase = get_db_connection()

    def read_and_merge(files):
        """
        Parser untuk file raw 'LH Recog/Request' (sheet 'direct,coe,self'), sama
        seperti yang dipakai learningHour.py - karena memang sumber file mentahnya
        SAMA. Bedanya, di sini kita ambil kolom tambahan yang dibutuhkan Expert
        Level (company, event, prof_level) yang tidak dipakai di Learning Hour.
        """
        all_data = []

        column_mapping = {
            "nik": "nik",
            "name": "expert",
            "company_name": "company",
            "course_name": "event",
            "activities": "variasi",
            "proficiency_level": "prof_level",
            "pl expert": "expert_level",  
            "month": "month",
            "year": "year",
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

            # Hitung Quarter otomatis dari kolom month (konsisten dengan learningHour.py)
            def month_to_quarter(m):
                try:
                    m = int(m)
                except (TypeError, ValueError):
                    return None
                if 1 <= m <= 3:
                    return "Q1"
                elif 4 <= m <= 6:
                    return "Q2"
                elif 7 <= m <= 9:
                    return "Q3"
                elif 10 <= m <= 12:
                    return "Q4"
                return None

            df["quarter"] = df["month"].apply(month_to_quarter)

            all_data.append(df)

        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            return combined
        return pd.DataFrame()

    st.title("Expert Level Score")

    options = ["Upload file", "From Data Base"]
    mode = st.pills("Data Resource", options, selection_mode="single", default="From Data Base")

    if mode == "Upload file":
        st.header("📁 Upload File")

        quarter_upload = st.selectbox("Quarter untuk data ini", ["Q1", "Q2", "Q3", "Q4"])

        uploaded_files = st.file_uploader("Upload data (format Excel)", accept_multiple_files=True, type=["xls", "xlsx"])
        if uploaded_files:
            parsed_df = read_and_merge(uploaded_files)
            if not parsed_df.empty:
                parsed_df["quarter"] = quarter_upload
            st.session_state["combined_df"] = parsed_df
            st.session_state["expert_level_quarter"] = quarter_upload
        combined_df = st.session_state.get("combined_df", pd.DataFrame())
        quarter = st.session_state.get("expert_level_quarter", quarter_upload)
    else:
        combined_df = load_all_data("learning_hour")

    if combined_df.empty:
        st.info("Tidak terdapat data")
        return

    st.dataframe(combined_df)

    if mode == "From Data Base":
        quarters = ["Q1", "Q2", "Q3", "Q4"]
        quarter = st.pills("Pilih Quarter", quarters, selection_mode="single", default="Q1")

        if "quarter" in combined_df.columns:
            combined_df = combined_df[combined_df["quarter"] == quarter]
        elif "Quarter" in combined_df.columns:
            combined_df = combined_df[combined_df["Quarter"] == quarter]

    if combined_df.empty:
        st.info(f"Tidak ada data untuk {quarter}. Pilih quarter lain yang sesuai dengan data yang diupload.")
        return

    required_cols = ["nik", "expert", "company", "event", "variasi", "prof_level", "expert_level"]
    missing_cols = [c for c in required_cols if c not in combined_df.columns]
    if missing_cols:
        st.error(
            f"Kolom berikut tidak ditemukan setelah filter: {missing_cols}. "
            "Pastikan file yang diupload sesuai format 'LH Recog/Request' (sheet 'direct,coe,self'), "
            "termasuk kolom 'PL Expert' (kolom AD) untuk level/seniority expert."
        )
        return

    main_df = combined_df[required_cols].copy()

    if "id" in combined_df.columns:
        main_df["id"] = combined_df["id"]

    main_df["expert_level"] = main_df["expert_level"].fillna(0)

    def map_bobot_expert(level):
        if pd.isna(level) or level == 0:
            return 0
        elif level in [1, 2]:
            return 0
        elif level == 3:
            return 1.0
        elif level == 4:
            return 1.2
        elif level == 5:
            return 1.4
        else:
            return 0

    main_df["bobot_expert"] = main_df["expert_level"].apply(map_bobot_expert)

    def map_bobot_program(prof_level):
        if pd.isna(prof_level) or prof_level == 0:
            return 0
        elif prof_level in [1, 2]:
            return 1.0
        elif prof_level == 3:
            return 1.2
        elif prof_level >= 4:
            return 1.4
        else:
            return 0

    main_df["bobot_program"] = main_df["prof_level"].apply(map_bobot_program)

    main_df["expert_level_score"] = (main_df["bobot_program"] * main_df["bobot_expert"]).round(4) * experLevel_PERSEN

    # === Final Expert Level per expert ===
    # PENTING: expert_level_score DIHITUNG SEKALI PER JENIS ASSIGNMENT ('variasi'),
    # bukan per baris/repetisi training. Kalau expert 3x Teaching (skor sama-sama
    # 14.4), itu tetap dihitung 1x untuk Teaching - bukan 14.4+14.4+14.4. Ini
    # konsisten dengan pola di variation.py (Variasi Penugasan), di mana repetisi
    # jenis yang sama tidak melipatgandakan skor.
    #
    # Kalau satu jenis assignment (misal 'Teaching') muncul berkali-kali dengan
    # Proficiency Level yang BERBEDA (sehingga expert_level_score-nya juga beda),
    # yang diambil adalah kemunculan PERTAMA untuk jenis itu (keep='first').
    deduped_per_jenis = main_df.drop_duplicates(subset=["nik", "expert", "variasi"], keep="first")

    agg_expert = deduped_per_jenis.groupby(["nik", "expert"], as_index=False).agg(
        total_expert_level_score=("expert_level_score", "sum"),
        jumlah_jenis_assignment=("variasi", "nunique"),
    )
    agg_expert["jumlah_jenis_assignment"] = agg_expert["jumlah_jenis_assignment"].replace(0, 1)
    agg_expert["final_expert_level"] = (
        agg_expert["total_expert_level_score"] / agg_expert["jumlah_jenis_assignment"]
    ).round(2)

    main_df = main_df.merge(
        agg_expert[["nik", "expert", "total_expert_level_score", "jumlah_jenis_assignment", "final_expert_level"]],
        on=["nik", "expert"], how="left",
    )

    spacer_l, col1, col2, spacer_r = st.columns([1, 2, 2, 1])
    col1.metric("Total Training", len(main_df), border=True)
    col2.metric("Total Expert", main_df["expert"].nunique(), border=True)

    st.subheader("📋 Detail Perhitungan Expert Level")
    st.caption(
        "'Final Expert Level' dihitung dari SKOR PER JENIS ASSIGNMENT (dedup - tiap "
        "jenis cuma dihitung 1x meski diulang berkali-kali), dijumlahkan lalu dibagi "
        "jumlah jenis unik. Baris di tabel ini tetap menampilkan SEMUA training mentah "
        "(termasuk yang berulang), tapi kolom 'Final Expert Level' sudah pakai angka "
        "yang benar (dedup)."
    )
    detail_df = main_df[[
        "nik", "expert", "prof_level", "bobot_program", "expert_level", "bobot_expert",
        "expert_level_score", "jumlah_jenis_assignment", "final_expert_level",
    ]].rename(
        columns={
            "prof_level": "Proficiency Level",
            "bobot_program": "Bobot Proficiency Level",
            "expert_level": "PL Expert",
            "bobot_expert": "Bobot PL Expert",
            "expert_level_score": "Expert Level",
            "jumlah_jenis_assignment": "Jumlah Jenis Assignment",
            "final_expert_level": "Final Expert Level",
        }
    )
    # Kelompokkan baris-baris dengan NIK yang sama supaya menempel berurutan,
    # TANPA mengubah urutan NIK itu sendiri (dipertahankan sesuai kemunculan
    # pertama di data, bukan diurutkan kecil-besar).
    urutan_nik = list(dict.fromkeys(detail_df["nik"]))
    detail_df["nik"] = pd.Categorical(detail_df["nik"], categories=urutan_nik, ordered=True)
    detail_df = detail_df.sort_values(by="nik", kind="stable").reset_index(drop=True)
    detail_df["nik"] = detail_df["nik"].astype(int)
    st.dataframe(detail_df, use_container_width=True)


    st.subheader("📊 Rekap Final Expert Level per Expert")
    rekap = agg_expert.sort_values(by="final_expert_level", ascending=False).reset_index(drop=True)
    rekap["nik"] = rekap["nik"].astype(int)

    rekap_display = rekap.rename(columns={
        "nik": "NIK",
        "expert": "Nama Expert",
        "total_expert_level_score": "Total Expert Level Score",
        "jumlah_jenis_assignment": "Jumlah Jenis Assignment",
        "final_expert_level": "Final Expert Level",
    })
    st.dataframe(rekap_display, use_container_width=True, hide_index=True)

    # === DOWNLOAD EXCEL (Detail + Rekap dalam 1 file, 2 sheet) ===
    if st.button("Download Hasil Expert Level (Excel)", key="btn_download_expert_level"):
        detail_download = main_df[[
            "nik", "expert", "company", "event", "variasi", "prof_level", "bobot_program",
            "expert_level", "bobot_expert", "expert_level_score",
            "jumlah_jenis_assignment", "final_expert_level",
        ]].copy()

        rekap_download = rekap[[
            "nik", "expert", "total_expert_level_score",
            "jumlah_jenis_assignment", "final_expert_level",
        ]].copy()

        import io
        buffer = io.BytesIO()

        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            detail_download.to_excel(writer, sheet_name="Detail", index=False)
            rekap_download.to_excel(writer, sheet_name="Rekap", index=False)

        buffer.seek(0)

        st.download_button(
            label="Download Expert_Level.xlsx",
            data=buffer,
            file_name=f"Expert_Level_{quarter}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.download_button(
        "Download rekap CSV",
        data=rekap_display.to_csv(index=False).encode("utf-8"),
        file_name="expert_level_summary.csv",
        mime="text/csv",
    )

    if st.button("💾 Simpan Expert Level Score ke Database", key="btn_save_expert"):
        try:
            df_save = rekap[["nik", "expert", "final_expert_level"]].copy()
            df_save["quarter"] = quarter
            df_save = df_save.rename(columns={"final_expert_level": "expert_level"})

            inserted = 0
            updated = 0
            
            for _, row in df_save.iterrows():
                existing = supabase.table("calculated").select("id").eq("nik", int(row["nik"])).eq("expert", row["expert"]).eq("quarter", row["quarter"]).execute()
                
                if existing.data:
                    supabase.table("calculated").update({
                        "expert_level": float(row["expert_level"]),
                        "final_expert_level": float(row["expert_level"]),
                    }).eq("nik", int(row["nik"])).eq("expert", row["expert"]).eq("quarter", row["quarter"]).execute()
                    updated += 1
                else:
                    supabase.table("calculated").insert({
                        "nik": int(row["nik"]),
                        "expert": row["expert"],
                        "quarter": row["quarter"],
                        "expert_level": float(row["expert_level"]),
                        "final_expert_level": float(row["expert_level"]),
                    }).execute()
                    inserted += 1

            st.success(f"✅ {inserted} insert + {updated} update untuk {quarter} (Rekap Expert Level)")

            
            if "id" in main_df.columns:
                detail_save_df = main_df[
                    ["id", "bobot_program", "bobot_expert", "expert_level_score"]
                ].copy()
                detail_save_df = detail_save_df.rename(columns={
                    "bobot_program": "bobot_proficiency_level",
                    "bobot_expert": "bobot_pl_expert",
                    "expert_level_score": "expert_level",
                })
                # Ganti NaN jadi None - NaN bukan JSON valid dan bikin update gagal
                detail_save_df = detail_save_df.astype(object).where(pd.notna(detail_save_df), None)

                updated_rows = 0
                for _, row in detail_save_df.iterrows():
                    supabase.table("learning_hour").update({
                        "bobot_proficiency_level": row["bobot_proficiency_level"],
                        "bobot_pl_expert": row["bobot_pl_expert"],
                        "expert_level": row["expert_level"],
                    }).eq("id", row["id"]).execute()
                    updated_rows += 1

                st.success(f"✅ {updated_rows} baris di tabel 'learning_hour' berhasil diupdate dengan hasil kalkulasi Expert Level")
            else:
                st.warning(
                    "⚠️ Data ini berasal dari mode 'Upload file' (belum tersimpan sebagai baris "
                    "di tabel 'learning_hour'), jadi hasil kalkulasi per-baris tidak bisa langsung "
                    "di-update ke tabel tersebut. Untuk update baris learning_hour, gunakan mode "
                    "'From Data Base' setelah data mentahnya masuk ke database."
                )

            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    expertLevel()