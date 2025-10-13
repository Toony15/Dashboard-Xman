# dataManager.py
import streamlit as st
import pandas as pd
from dbConfig import get_db_connection
import io
import st_aggrid
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

def init_aggrid(df, grid_key=None, thousand_columns=[], use_selection=False, height=600, width='100%', selection_mode='single'):
    """
        click_event_callback (callable, optional): A function to be called when a row is clicked.
        returns the [_, selected_row] -> selected_row is a filtered df
    """
    if df is None or len(df)==0 or df.empty:
        st.write("No data to show")
        return None,None

    # Round numeric columns to 3 decimal places
    df = df.copy()
    numeric_cols = df.select_dtypes(include='number').columns
    df[numeric_cols] = df[numeric_cols].round(3)

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_grid_options(domLayout='normal')

    if use_selection:
        gb.configure_selection(selection_mode=selection_mode, use_checkbox=False, groupSelectsChildren=False)
    
    k_sep_formatter = st_aggrid.JsCode("""
        function(params) {
            return (params.value == null) ? params.value : params.value.toLocaleString(); 
        }
    """)
    gb.configure_columns(thousand_columns, valueFormatter=k_sep_formatter)

    gridOptions = gb.build()

    # Inject inline CSS for font size
    gridOptions['domLayout'] = 'normal' # Ensure layout is normal
    gridOptions['rowHeight'] = 33
    gridOptions['defaultColDef'] = {
        'cellStyle': {
            'font-size': '15px',
        },
        'headerClass': 'ag-header-cell',
        'resizable': True,
    }
    gridOptions['autoSizeStrategy'] = {
        'type': 'fitGridWidth',
        'defaultMinWidth': 190,
    }
    
    grid_response = AgGrid(
        df,
        gridOptions=gridOptions,
        height=height,
        width=width,
        update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.MODEL_CHANGED,
        data_return_mode='AS_INPUT',
        allow_unsafe_jscode=True,
        key=grid_key,
        #columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        enable_enterprise_modules=False
    )

    selected_row = None
    print(grid_response)
    if grid_response['selected_rows'] is not None and len(grid_response['selected_rows']) > 0:
        selected_row = grid_response['selected_rows']
        selected_row = selected_row.to_dict(orient='records')
    

    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="data_export.csv",
        mime="text/csv",
    )
    return [grid_response,selected_row]



def show_data_manager():
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
        optionRead = ["Learning Impact 1", "Learning Hours", "Variation"]
        tableName = st.pills("Action", optionRead, selection_mode="single", default="Learning Impact 1")
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
            _, selected_row = init_aggrid(df,use_selection=True,selection_mode='single')
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