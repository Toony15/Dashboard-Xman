import streamlit as st
from modules.performanceIndex import performanceIndexPage

st.set_page_config(page_title="Performance Index", layout="wide")
performanceIndexPage()
