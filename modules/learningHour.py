import streamlit as st
import pandas as pd
import io
from dbConfig import get_db_connection
from google import genai
from dataManager import load_all_data

def learning_hour_page():
    print("halaman learning hour")