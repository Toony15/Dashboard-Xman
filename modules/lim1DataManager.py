import streamlit as st

def uploadLim1(combined_df, DestinationTable, supabase, upload):
            if upload == True:
                try:
                    df = combined_df[["id","Email","Event","Question","Answer","Expert","Unit","Quarter"]]

                    # Upload baris demi baris ke tabel Supabase
                    data = df.to_dict(orient="records")
                    total_rows = len(data)

                    if total_rows == 0:
                        st.warning("⚠️ Tidak ada data untuk diupload.")
                    else:
                        st.info(f"⏳ Mengupload {total_rows} baris ke tabel '{DestinationTable}'...")
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        # Upload satu per satu dengan progress bar
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