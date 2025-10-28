# dataManager.py
import streamlit as st
import pandas as pd
from dbConfig import get_db_connection
import io
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
from st_aggrid import GridUpdateMode
from modules.lim1DataManager import uploadLim1

supabase = get_db_connection()
def load_all_data(table_name, batch_size=1000):
        all_data = []
        last_id = None
        total_fetched = 0

        st.info(f"⏳ Mengambil seluruh data dari tabel '{table_name}'...")
        progress = st.progress(0)
        progress_text = st.empty()

        while True:
            # Query batch dengan urutan id naik
            query = supabase.table(table_name).select("*").order("id", desc=False).limit(batch_size)
            
            # Ambil data setelah id terakhir di batch sebelumnya
            if last_id is not None:
                query = query.gt("id", last_id)
            
            response = query.execute()
            data = response.data

            if not data:
                break  # Sudah tidak ada data

            all_data.extend(data)
            total_fetched += len(data)
            last_id = data[-1]["id"]  # Simpan ID terakhir dari batch

            # Update progress bar
            # Karena kita tidak tahu total pasti, kita buat animasi incremental 0–90%
            progress.progress(min(0.9, total_fetched / (total_fetched + batch_size)))
            progress_text.text(f"📦 Mengambil data... Total {total_fetched} baris diambil.")

            # Jika jumlah data < batch_size → artinya sudah selesai
            if len(data) < batch_size:
                break

        # Tutup progress bar
        progress.progress(1.0)
        progress_text.text("✅ Pengambilan data selesai!")

        # Konversi ke DataFrame
        df = pd.DataFrame(all_data)

        # Urutkan untuk memastikan konsistensi
        if "id" in df.columns:
            df = df.sort_values("id").reset_index(drop=True)

        st.success(f"✅ Berhasil memuat {len(df)} data unik dari '{table_name}'.")
        return df

def show_data_manager():
    supabase = get_db_connection()
    def init_aggrid(
        df, 
        grid_key=None, 
        thousand_columns=[], 
        use_selection=False, 
        height=600, 
        width='100%', 
        selection_mode='single'
    ):
        """
        Menampilkan dataframe dalam tabel interaktif AG Grid.
        Mengembalikan [grid_response, selected_row].
        """

        # 🧱 Validasi data
        if df is None or df.empty:
            st.info("Tidak ada data untuk ditampilkan.")
            return None, None

        # 🔢 Pembulatan angka
        df = df.copy()
        numeric_cols = df.select_dtypes(include='number').columns
        df[numeric_cols] = df[numeric_cols].round(3)

        # 🧩 Setup Grid
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_grid_options(domLayout='normal')

        if use_selection:
            gb.configure_selection(
                selection_mode=selection_mode,
                use_checkbox=False,
                groupSelectsChildren=False
            )

        # 💬 Format angka ribuan (jika diperlukan)
        if thousand_columns:
            gb.configure_columns(thousand_columns, valueFormatter="""
                function(params) {
                    return (params.value == null) ? params.value : params.value.toLocaleString();
                }
            """)

        # ⚙️ Build opsi grid
        gridOptions = gb.build()
        gridOptions['domLayout'] = 'normal'
        gridOptions['rowHeight'] = 33
        gridOptions['defaultColDef'] = {
            'cellStyle': {'font-size': '15px'},
            'headerClass': 'ag-header-cell',
            'resizable': True,
        }
        gridOptions['autoSizeStrategy'] = {
            'type': 'fitGridWidth',
            'defaultMinWidth': 190,
        }

        # 🧾 Render grid
        grid_response = AgGrid(
            df,
            gridOptions=gridOptions,
            height=height,
            width=width,
            update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.VALUE_CHANGED,
            data_return_mode='AS_INPUT',
            allow_unsafe_jscode=True,
            key=grid_key,
            enable_enterprise_modules=False
        )

        # ✅ Ambil baris yang dipilih
        selected_row = None
        if grid_response is not None and len(grid_response.get('selected_rows', [])) > 0:
            selected_row = pd.DataFrame(grid_response['selected_rows'])
            selected_row_df = pd.DataFrame(grid_response['selected_rows'])
            selected_id = selected_row_df['id'].iloc[0]  # ambil scalar
            selected_row = df[df["id"] == selected_id].iloc[0]
            # selected_id = selected_row.iloc[0]['id'] if 'id' in selected_row.columns else None
        else:
            selected_row, selected_id = None, None

        # 💾 Tombol download
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="data_export.csv",
            mime="text/csv",
        )

        return grid_response, selected_row, selected_id
    
    st.title("🗃️ Data Manager")
    supabase = get_db_connection()
    options = ["Upload Data", "Lihat Data", "Edit Data"]
    menu = st.pills("Action", options, selection_mode="single", default="Upload Data")

    # --- 🟢 UPLOAD DATA ---
    if menu == "Upload Data":
        st.subheader("📤 Upload File Excel ke Database")

        uploaded_file = st.file_uploader(
            "Upload data (format Excel)", 
            accept_multiple_files=True, 
            type=["xls", "xlsx"]
        )
        
        def read_and_merge(files, table_name):
            all_data = []
            # 1️⃣ Ambil ID terakhir dari database
            try:
                response = supabase.table(table_name).select("id").order("id", desc=True).limit(1).execute()
                if response.data:
                    last_id = response.data[0]["id"]
                else:
                    last_id = 0
            except Exception as e:
                st.warning(f"Gagal mengambil ID terakhir dari database: {e}")
                last_id = 0

            id_counter = last_id + 1  # mulai dari id terakhir + 1
            
            # 2️⃣ Peta kolom alternatif ke nama sesuai DB Supabase
            if table_name == "learningImpact1":
                column_mapping = {
                    "id": "id",
                    "email": "Email",
                    "email address": "Email",
                    "Email": "Email",
                    "question": "Question",
                    "cleaned_question": "Question",
                    "soal": "Question",
                    "answer": "Answer",
                    "cleaned_answer": "Answer",
                    "response": "Answer",
                }
                # 3️⃣ Kolom target sesuai tabel Supabase
                required_columns = ["id", "Email", "Event", "Question", "Answer", "Expert", "Unit", "Quarter"]
            elif table_name == "learningHours":
                column_mapping = {
                    "id":"id"
                }
            elif table_name == "event":
                column_mapping = {
                    "id":"id"
                }
            for uploaded_file in files:
                try:
                    df = pd.read_excel(uploaded_file)
                except Exception as e:
                    st.error(f"Gagal membaca file {uploaded_file.name}: {e}")
                    continue
                # Normalisasi nama kolom → lowercase dan strip spasi
                df.columns = [col.strip().lower() for col in df.columns]

                # Mapping nama kolom agar cocok dengan struktur Supabase
                df.rename(columns=lambda c: column_mapping.get(c.lower(), c), inplace=True)

                # Ambil nama file tanpa ekstensi
                file_name = uploaded_file.name.rsplit(".", 1)[0]
                parts = file_name.split("_")
                event, expert, unit, quarter = (parts + ["", "", "", ""])[:4]
                
                # Isi kolom yang hilang agar tetap sesuai struktur tabel
                for col in required_columns:
                    if col not in df.columns:
                        df[col] = ""

                # Tambahkan kolom metadata
                df["Event"] = event
                df["Expert"] = expert
                df["Unit"] = unit
                df["Quarter"] = quarter
                df["id"] = range(id_counter, id_counter + len(df))
                id_counter += len(df)
                all_data.append(df)

            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                combined["Event"] = combined["Event"].fillna("").astype(str).str.strip()
                combined = combined.fillna("empty").replace("", "empty")
                return combined
            else:
                return pd.DataFrame()

        tableName = st.radio("Pilih destinasi:", ["Learning Impact 1", "Learning Hours", "Variation"])
        if tableName == "Learning Impact 1":
            DestinationTable = "learningImpact1"
             # Simpan hasil upload ke session_state agar tidak hilang setelah interaksi
            if uploaded_file:
                st.session_state["combined_df"] = read_and_merge(uploaded_file, DestinationTable)
            # Ambil data dari session_state
            combined_df = st.session_state.get("combined_df", pd.DataFrame())
            st.dataframe(combined_df)
            if uploaded_file and st.button("Upload ke Database", key="upload_Lim1"):
                try:
                    upload = True
                    uploadLim1(combined_df, DestinationTable, supabase, upload)
                except Exception as e:
                    st.error(f"❌ Gagal upload: {e}")
        elif tableName == "Learning Hours":
            viewTable = "none"
        elif tableName == "Variation":
            DestinationTable = "none"

    # --- 🔵 READ DATA ---
    elif menu == "Lihat Data":
        st.subheader("📖 Lihat Data dari Database")
        optionRead = ["Learning Impact 1", "Learning Hours", "Variation"]
        tableName = st.pills("Action", optionRead, selection_mode="single", default="Learning Impact 1")
        if tableName == "Learning Impact 1":
            viewTable = "learningImpact1"
        elif tableName == "Learning Hours":
            viewTable = "learningHour"
        else:
            viewTable = "none"

        if st.button("Tampilkan Data"):
            try:
                response = supabase.table(viewTable).select("*").execute()
                df = load_all_data(viewTable)

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
                df = load_all_data(table_name)

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
            # df["Aksi"] = ["Pilih" for _ in range(len(df))]
            # st.data_editor(
            #     df,
            #     key="data_preview",
            #     use_container_width=True,
            #     hide_index=True,
            #     disabled=True,
            #     column_config={
            #         "ID": st.column_config.TextColumn("ID", disabled=True),
            #         "Aksi": st.column_config.TextColumn("Aksi", help="Klik tombol di bawah untuk memilih")
            #     },
            # )
            
            # st.dataframe(df)

            # # Pilih baris berdasarkan ID
            # selected_id = st.selectbox("Pilih ID untuk diubah / hapus:", df["id"])

            # # Ambil data baris terpilih
            # selected_row = df[df["id"] == selected_id].iloc[0]
            _, selected_row, selected_id= init_aggrid(df,use_selection=True,selection_mode='single')
            # selected_id = selectedRow["id"]
            # selected_row = df[df["id"] == selected_id].iloc[0]
            st.markdown("### 📝 Ubah Data")
            updated_data = {}
            editContainer = st.container(
                horizontal = True
            )
            with editContainer:
                # Buat input dinamis berdasarkan kolom (kecuali id)
                for col in df.columns:
                    if col == "id":
                        st.text_input("ID", str(selected_row[col]), width=40, disabled=True)
                        continue
                    elif col in ["Unit", "Quarter"]:
                        # Input dinamis
                        val = st.text_input(f"{col}", str(selected_row[col]), width=60)
                        updated_data[col] = val
                    elif col == "Answer":
                        if len(str(selected_row["Answer"])) <= 2:
                            val = st.text_input(f"{col}", str(selected_row[col]), width=60)
                            updated_data[col] = val
                        else:
                            val = st.text_area(f"{col}", str(selected_row[col]))
                            updated_data[col] = val
                    elif col in ["Expert"]:
                        # Input dinamis
                        val = st.text_input(f"{col}", str(selected_row[col]), width=150)
                        updated_data[col] = val
                    else:
                        # Input dinamis
                        val = st.text_area(f"{col}", str(selected_row[col]))
                        updated_data[col] = val

            buttonContainer = st.container(
                horizontal = True
            )
            with buttonContainer:
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