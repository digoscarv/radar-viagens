import requests
from datetime import date, timedelta


def get_cotacao_brl(moeda: str) -> float:
    """
    Retorna a cotação atual da moeda estrangeira em relação ao Real (BRL).
    Retorna 1.0 se a moeda já for BRL.
    """
    if moeda == "BRL":
        return 1.0

    url = f"https://economia.awesomeapi.com.br/last/{moeda}-BRL"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        chave = f"{moeda}BRL"
        if chave in data:
            return float(data[chave]["bid"])
    except Exception as e:
        print(f"Aviso: Falha ao buscar cotação de {moeda} ({e}). Usando valor de referência.")

    # Fallbacks caso a API oscile
    fallbacks = {"USD": 5.60, "EUR": 6.10, "GBP": 7.20, "JPY": 0.038}
    return fallbacks.get(moeda, 1.0)


def gerar_link_google_flights(origem_iata: str, destino_iata: str, data_ida: date, dias: int) -> str:
    """
    Gera um link direto e limpo para o Google Flights sem viés de cookies ou afiliados.
    """
    data_volta = data_ida + timedelta(days=dias)
    ida_str = data_ida.strftime("%Y-%m-%d")
    volta_str = data_volta.strftime("%Y-%m-%d")
    
    return f"https://www.google.com/travel/flights?q=Flights%20to%20{destino_iata}%20from%20{origem_iata}%20on%20{ida_str}%20through%20{volta_str}"