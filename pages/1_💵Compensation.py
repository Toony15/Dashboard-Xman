import streamlit as st
from modules.compensation import compensation_page

st.set_page_config(page_title="Compensation", layout="wide")
compensation_page()
