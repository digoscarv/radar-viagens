import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Erro: SUPABASE_URL ou SUPABASE_KEY não configuradas.")
    exit(1)

# Faz uma consulta simples à tabela destinos via PostgREST
endpoint = f"{SUPABASE_URL}/rest/v1/destinos?select=id,cidade&limit=1"
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

try:
    response = requests.get(endpoint, headers=headers, timeout=10)
    response.raise_for_status()
    print(f"Sucesso! Supabase ativo. Destino lido: {response.json()}")
except Exception as e:
    print(f"Falha ao consultar o Supabase: {e}")
    exit(1)