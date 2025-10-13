import streamlit as st
from modules.satisfactionRate import satisfaction_page

st.set_page_config(page_title="Learning Impact 1", layout="wide")
satisfaction_page()
