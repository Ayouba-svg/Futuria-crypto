import matplotlib
matplotlib.use('Agg')  # Nécessaire pour Pydroid3 (pas d'affichage interactif)
import matplotlib.pyplot as plt
from data import get_market_data
from indicators import calculate_indicators

def generate_chart(coin, days=60, save_path=None):
    """
    Génère un graphique complet : prix + SMA + Bollinger + RSI
    Sauvegarde en image PNG dans le dossier du projet
    """
    df = get_market_data(coin, days=days)
    df = calculate_indicators(df)

    if save_path is None:
        save_path = f"/storage/emulated/0/FuturIA_Crypto/{coin}_chart.png"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), height_ratios=[3, 1])

    # --- Graphique du haut : prix + SMA + Bollinger ---
    ax1.plot(df['close'], label='Prix', color='white', linewidth=1.5)
    ax1.plot(df['sma20'], label='SMA 20', color='orange', linewidth=1)
    ax1.plot(df['sma50'], label='SMA 50', color='cyan', linewidth=1)
    ax1.plot(df['bb_high'], label='Bollinger haut', color='gray', linestyle='--', linewidth=0.8)
    ax1.plot(df['bb_low'], label='Bollinger bas', color='gray', linestyle='--', linewidth=0.8)
    ax1.fill_between(df.index, df['bb_low'], df['bb_high'], alpha=0.1, color='gray')
    ax1.set_title(f"{coin.upper()} - Analyse technique", color='white')
    ax1.legend(loc='upper left', fontsize=8)
    ax1.grid(alpha=0.2)
    ax1.set_facecolor('black')

    # --- Graphique du bas : RSI ---
    ax2.plot(df['rsi'], color='purple', linewidth=1.2)
    ax2.axhline(70, color='red', linestyle='--', linewidth=0.8)
    ax2.axhline(30, color='green', linestyle='--', linewidth=0.8)
    ax2.set_title("RSI", color='white')
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.2)
    ax2.set_facecolor('black')

    fig.patch.set_facecolor('black')
    plt.tight_layout()
    plt.savefig(save_path, dpi=120, facecolor='black')
    plt.close(fig)

    return save_path