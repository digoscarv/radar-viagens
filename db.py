import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# 1. Leitura de credenciais (Suporta tanto o .env local quanto os Secrets do Streamlit Cloud)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL and hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]

if not SUPABASE_KEY and hasattr(st, "secrets") and "SUPABASE_KEY" in st.secrets:
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL ou SUPABASE_KEY não configuradas no .env nem nos Secrets do Streamlit Cloud.")

# Cria o cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# 2. Funções de Consulta e Escrita no Banco

def get_destinos_ativos() -> list[dict]:
    """Busca todos os destinos cadastrados e ativos."""
    response = (
        supabase.table("destinos")
        .select("id, cidade, pais, regiao, moeda, iata_aeroporto")
        .eq("ativo", True)
        .order("cidade")
        .execute()
    )
    return response.data


def get_custos_por_destino(destino_id: int, perfil: str = "moderado") -> dict:
    """Busca os custos diários base para casal."""
    response = (
        supabase.table("custos_referencia")
        .select("categoria, valor_diario_moeda_local")
        .eq("destino_id", destino_id)
        .eq("perfil", perfil)
        .execute()
    )
    return {item["categoria"]: float(item["valor_diario_moeda_local"]) for item in response.data}


def get_sazonalidade_destino(destino_id: int) -> list[dict]:
    """Busca os dados de sazonalidade, clima e média de passagens dos 12 meses."""
    try:
        response = (
            supabase.table("sazonalidade_mensal")
            .select("mes, estacao, tipo_temporada, fator_multiplicador, temp_media_celsius, dias_chuva_media, passagem_media_brl, descricao_periodo")
            .eq("destino_id", destino_id)
            .order("mes")
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Erro ao buscar sazonalidade: {e}")
        return []


def salvar_simulacao(dados: dict) -> bool:
    """Grava uma simulação na tabela simulacoes_viagem."""
    try:
        supabase.table("simulacoes_viagem").insert(dados).execute()
        return True
    except Exception as e:
        print(f"Erro ao salvar simulação: {e}")
        return False


def get_simulacoes_salvas() -> list[dict]:
    """Busca todas as simulações salvas no banco com dados do destino."""
    try:
        response = (
            supabase.table("simulacoes_viagem")
            .select("id, titulo_viagem, data_prevista_inicio, duracao_dias, perfil_escolhido, cotacao_moeda_brl, total_estimado_moeda_local, total_estimado_brl, link_google_flights, notas, autor, created_at, destinos(cidade, pais, moeda)")
            .order("created_at", desc=True)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Erro ao buscar simulações: {e}")
        return []


def excluir_simulacao(simulacao_id: str) -> bool:
    """Exclui uma simulação salva."""
    try:
        supabase.table("simulacoes_viagem").delete().eq("id", simulacao_id).execute()
        return True
    except Exception as e:
        print(f"Erro ao excluir simulação: {e}")
        return False


def get_atracoes_por_destino(destino_id: int) -> list[dict]:
    """Busca as atrações e dicas de um destino."""
    try:
        response = (
            supabase.table("atracoes")
            .select("nome, categoria, custo_moeda_local, horario_funcionamento, dicas")
            .eq("destino_id", destino_id)
            .order("categoria")
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Erro ao buscar atrações: {e}")
        return []


def get_roteiro_por_simulacao(simulacao_id: str) -> list[dict]:
    """Busca as atividades do roteiro de uma viagem."""
    try:
        response = (
            supabase.table("roteiro_itens")
            .select("id, dia, periodo, atividade, autor, created_at")
            .eq("simulacao_id", simulacao_id)
            .order("dia")
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Erro ao buscar roteiro: {e}")
        return []


def adicionar_item_roteiro(dados: dict) -> bool:
    """Insere uma atividade no roteiro."""
    try:
        supabase.table("roteiro_itens").insert(dados).execute()
        return True
    except Exception as e:
        print(f"Erro ao adicionar item: {e}")
        return False


def excluir_item_roteiro(item_id: int) -> bool:
    """Remove uma atividade do roteiro."""
    try:
        supabase.table("roteiro_itens").delete().eq("id", item_id).execute()
        return True
    except Exception as e:
        print(f"Erro ao excluir item: {e}")
        return False