from supabase import create_client
import streamlit as st

# Ambil kredensial dari Streamlit Secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

def init_connection():
    """Inisialisasi koneksi ke Supabase"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Buat instance global agar tidak reconnect terus
supabase = init_connection()