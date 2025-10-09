# dataManager.py
import streamlit as st
import pandas as pd
from dbConfig import get_db_connection
import io

def show_data_manager():
    st.title("🗃️ Data Manager (Upload, Read, Edit)")
    supabase = get_db_connection()

    menu = st.radio("Pilih Aksi:", ["Upload Data", "Lihat Data", "Edit Data"])

    # --- 🟢 UPLOAD DATA ---
    if menu == "Upload Data":
        st.subheader("📤 Upload File Excel ke Database")

        uploaded_file = st.file_uploader(
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
                event, expert, unit, quarter = (parts + ["", "", "", ""])[:4]

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

        # Simpan hasil upload ke session_state agar tidak hilang setelah interaksi
        if uploaded_file:
            st.session_state["combined_df"] = read_and_merge(uploaded_file)

        # Ambil data dari session_state
        combined_df = st.session_state.get("combined_df", pd.DataFrame())
        st.dataframe(combined_df)
        
        tableName = st.radio("Pilih destinasi:", ["Learning Impact 1", "Learning Hours", "Variation"])
        if tableName == "Learning Impact 1":
            DestinationTable = "learningImpact1"
        else:
            viewTable = "none"

        if uploaded_file and st.button("Upload ke Database"):
            try:
                df = combined_df[["id","Email","Event","Question","Answer","Expert","Unit","Quarter"]]

                # Upload baris demi baris ke tabel Supabase
                data = df.to_dict(orient="records")
                for row in data:
                    supabase.table(DestinationTable).insert(row).execute()

                st.success(f"✅ Berhasil upload {len(data)} baris ke tabel '{DestinationTable}'")
                st.dataframe(df)
            except Exception as e:
                st.error(f"Gagal upload: {e}")

    # --- 🔵 READ DATA ---
    elif menu == "Lihat Data":
        st.subheader("📖 Lihat Data dari Database")
        tableName = st.radio("Pilih Aksi:", ["Learning Impact 1", "Learning Hours", "Variation"])
        if tableName == "Learning Impact 1":
            viewTable = "learningImpact1"
        else:
            viewTable = "none"

        if st.button("Tampilkan Data"):
            try:
                response = supabase.table(viewTable).select("*").execute()
                df = pd.DataFrame(response.data)

                if df.empty:
                    st.warning("Tidak ada data di tabel ini.")
                else:
                    st.success(f"✅ Menampilkan {len(df)} baris data.")
                    st.dataframe(df)

                    # Tombol download
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        df.to_excel(writer, index=False, sheet_name="Data")
                    st.download_button(
                        label="💾 Download Data Excel",
                        data=buffer.getvalue(),
                        file_name=f"{viewTable}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            except Exception as e:
                st.error(f"Gagal membaca data: {e}")

    # --- 🟣 EDIT DATA ---
    elif menu == "Edit Data":
        # -----------------------------
        # PILIH TABEL
        # -----------------------------
        st.subheader("✏️ Edit / Hapus Data di Database")

        table_name = st.selectbox("Pilih Tabel:", ["learningImpact1", "learningHours", "variation"])

        # -----------------------------
        # MUAT DATA DARI SUPABASE
        # -----------------------------
        if st.button("📥 Muat Data"):
            try:
                response = supabase.table(table_name).select("*").execute()
                df = pd.DataFrame(response.data)

                if df.empty:
                    st.warning("Tidak ada data di tabel ini.")
                else:
                    st.session_state.df = df
                    st.success(f"✅ Data berhasil dimuat ({len(df)} baris)")
            except Exception as e:
                st.error(f"Gagal memuat data: {e}")

        # -----------------------------
        # TAMPILKAN DATA & PILIH BARIS
        # -----------------------------
        if "df" in st.session_state:
            df = st.session_state.df
            st.dataframe(df)

            # Pilih baris berdasarkan ID
            selected_id = st.selectbox("Pilih ID untuk diubah / hapus:", df["id"])

            # Ambil data baris terpilih
            selected_row = df[df["id"] == selected_id].iloc[0]

            st.markdown("### 📝 Ubah Data")
            updated_data = {}

            # Buat input dinamis berdasarkan kolom (kecuali id)
            for col in df.columns:
                if col == "id":
                    st.text_input("ID (tidak bisa diubah)", str(selected_row[col]), disabled=True)
                    continue
                else:
                    # Input dinamis
                    val = st.text_area(f"{col}", str(selected_row[col]))
                    updated_data[col] = val

            # -----------------------------
            # UPDATE DATA
            # -----------------------------
            if st.button("💾 Simpan Perubahan"):
                try:
                    response = supabase.table(table_name).update(updated_data).eq("id", selected_id).execute()
                    st.success("✅ Data berhasil diperbarui!")
                    st.session_state.df.loc[df["id"] == selected_id, list(updated_data.keys())] = list(updated_data.values())
                except Exception as e:
                    st.error(f"🚨 Gagal memperbarui data: {e}")

            # -----------------------------
            # DELETE DATA
            # -----------------------------
            if st.button("🗑️ Hapus Data Ini"):
                try:
                    response = supabase.table(table_name).delete().eq("id", selected_id).execute()
                    st.success("🗑️ Data berhasil dihapus!")
                    st.session_state.df = df[df["id"] != selected_id]
                except Exception as e:
                    st.error(f"🚨 Gagal menghapus data: {e}")