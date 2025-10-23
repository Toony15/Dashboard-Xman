import streamlit as st
from modules.variation import variation_page
from modules.newVariation import newVariationPage

st.set_page_config(page_title="Variation", layout="wide")
newVariationPage()
