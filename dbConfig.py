from supabase import create_client
import streamlit as st

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

def get_db_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def init_connection():
    """Inisialisasi koneksi ke Supabase"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Buat instance global agar tidak reconnect terus
supabase = init_connection()