import requests
import pandas as pd
import time
from config import COINGECKO_BASE_URL, VS_CURRENCY

def get_crypto(coin, max_retries=3):
    """Récupère prix + variation 24h, avec nouvelle tentative automatique"""
    url = f"{COINGECKO_BASE_URL}/simple/price"
    params = {"ids": coin, "vs_currencies": VS_CURRENCY, "include_24hr_change": "true"}

    for tentative in range(1, max_retries + 1):
        try:
            data = requests.get(url, params=params, timeout=10).json()

            if coin in data and VS_CURRENCY in data[coin]:
                price = data[coin][VS_CURRENCY]
                change = data[coin][f"{VS_CURRENCY}_24h_change"]
                return price, change

            print(f"⏳ Limite API atteinte pour {coin} (prix), tentative {tentative}/{max_retries}...")

        except requests.exceptions.ConnectionError:
            print(f"📡 Pas de connexion internet pour {coin} (prix), tentative {tentative}/{max_retries}...")
        except requests.exceptions.Timeout:
            print(f"⏱️ Délai dépassé pour {coin} (prix), tentative {tentative}/{max_retries}...")

        if tentative < max_retries:
            attente = 10 * tentative
            print(f"   → nouvelle tentative dans {attente}s...")
            time.sleep(attente)

    raise ValueError(f"Impossible de récupérer le prix pour {coin} après {max_retries} tentatives")

def get_market_data(coin, days=60, max_retries=3):
    """Récupère prix ET volume, avec nouvelle tentative automatique (rate-limit ou coupure réseau)"""
    url = f"{COINGECKO_BASE_URL}/coins/{coin}/market_chart"
    params = {"vs_currency": VS_CURRENCY, "days": days}

    for tentative in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "prices" in data:
                df_price = pd.DataFrame(data["prices"], columns=["timestamp", "close"])
                df_volume = pd.DataFrame(data["total_volumes"], columns=["timestamp", "volume"])
                df = df_price.merge(df_volume, on="timestamp")
                return df

            print(f"⏳ Limite API atteinte pour {coin}, tentative {tentative}/{max_retries}...")

        except requests.exceptions.ConnectionError:
            print(f"📡 Pas de connexion internet pour {coin}, tentative {tentative}/{max_retries}...")
        except requests.exceptions.Timeout:
            print(f"⏱️ Délai dépassé pour {coin}, tentative {tentative}/{max_retries}...")

        if tentative < max_retries:
            attente = 10 * tentative
            print(f"   → nouvelle tentative dans {attente}s...")
            time.sleep(attente)

    raise ValueError(f"Impossible de récupérer les données pour {coin} après {max_retries} tentatives (réseau ou API indisponible)")

def get_ohlc_dataframe(coin, days=30):
    return get_market_data(coin, days)