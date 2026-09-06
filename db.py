import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Tenta ler do .env local
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Se estiver na nuvem (Streamlit Cloud), lê de st.secrets
if not SUPABASE_URL and hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]

if not SUPABASE_KEY and hasattr(st, "secrets") and "SUPABASE_KEY" in st.secrets:
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ou SUPABASE_KEY não configuradas no .env nem nos Secrets do Streamlit Cloud.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)