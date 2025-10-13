import streamlit as st
from dataManager import show_data_manager

st.set_page_config(page_title="Data Manager", layout="wide")
show_data_manager()
