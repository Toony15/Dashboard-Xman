import streamlit as st
from modules.consistencyIndex import consistencyIndexPage

st.set_page_config(page_title="Consistency Index", layout="wide")
consistencyIndexPage()
