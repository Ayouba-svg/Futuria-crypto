import pandas as pd
from data import get_market_data
from indicators import calculate_indicators


def calculer_score(row):
    """
    Calcule le score, le signal et la confiance à partir d'une seule ligne
    d'indicateurs déjà calculés (row doit contenir : rsi, macd, macd_signal,
    sma20, sma50, close, bb_low, bb_high, volume, volume_sma).

    Fonction PURE (aucun appel réseau) : utilisée à la fois en direct par
    analyse_crypto_v2() et par backtest.py.

    CORRECTIF confiance : la confiance mesure maintenant le VRAI consensus
    entre indicateurs (poids des votes haussiers vs baissiers, hors votes
    neutres), et non plus "combien d'indicateurs ont voté" sans tenir
    compte de s'ils étaient d'accord entre eux. Un MACD haussier + une SMA
    baissière ne doivent PAS compter comme "2 signaux d'accord".
    """
    score = 50
    reasons = []

    bullish_weight = 0
    bearish_weight = 0
    total_weight = 0

    def vote(poids, haussier=None):
        nonlocal bullish_weight, bearish_weight, total_weight
        total_weight += poids
        if haussier is True:
            bullish_weight += poids
        elif haussier is False:
            bearish_weight += poids
        # haussier=None → neutre, ne compte dans aucun camp

    # --- RSI ---
    rsi_direction = "neutre"
    if row['rsi'] < 30:
        score += 15
        vote(15, True)
        rsi_direction = "haussier"
        reasons.append(f"RSI faible ({row['rsi']:.1f}) → zone de survente, rebond possible")
    elif row['rsi'] > 70:
        score -= 15
        vote(15, False)
        rsi_direction = "baissier"
        reasons.append(f"RSI élevé ({row['rsi']:.1f}) → zone de surachat, risque de correction")
    else:
        vote(15, None)
        reasons.append(f"RSI neutre ({row['rsi']:.1f})")

    # --- MACD ---
    macd_bullish = row['macd'] > row['macd_signal']
    if macd_bullish:
        score += 15
        vote(15, True)
        reasons.append("MACD au-dessus de sa ligne de signal → momentum haussier")
    else:
        score -= 15
        vote(15, False)
        reasons.append("MACD en dessous de sa ligne de signal → momentum baissier")

    # --- Tendance SMA ---
    sma_bullish = row['sma20'] > row['sma50']
    if sma_bullish:
        score += 10
        vote(10, True)
        reasons.append("Moyenne courte au-dessus de la longue → tendance haussière")
    else:
        score -= 10
        vote(10, False)
        reasons.append("Moyenne courte en dessous de la longue → tendance baissière")

    # --- Bandes de Bollinger ---
    if row['close'] <= row['bb_low']:
        score += 10
        vote(10, True)
        reasons.append("Prix proche de la bande basse → survente possible")
    elif row['close'] >= row['bb_high']:
        score -= 10
        vote(10, False)
        reasons.append("Prix proche de la bande haute → surachat possible")
    else:
        vote(10, None)
        reasons.append("Prix dans une zone normale (bandes de Bollinger)")

    # --- Volume : confirmation, pas de direction propre ---
    volume_confirme = row['volume'] > row['volume_sma']
    if volume_confirme:
        score += 5 if score >= 50 else -5
        reasons.append("Volume supérieur à la moyenne → mouvement confirmé")
    else:
        reasons.append("Volume inférieur à la moyenne → mouvement à confirmer")

    score = max(0, min(100, score))

    # --- Décision du signal (score + confirmation de tendance obligatoire) ---
    # Les indicateurs de tendance (RSI/MACD/SMA) doivent être alignés pour
    # valider un ACHAT/VENTE fort. Bollinger et Volume seuls ne suffisent pas.
    indicateurs_tendance_haussiers = sum([
        rsi_direction == "haussier",
        macd_bullish,
        sma_bullish
    ])
    indicateurs_tendance_baissiers = sum([
        rsi_direction == "baissier",
        not macd_bullish,
        not sma_bullish
    ])

    if score >= 70:
        if indicateurs_tendance_haussiers >= 2:
            signal = "🔥 ACHAT FORT"
        else:
            signal = "⚖️ ATTENDRE"
            reasons.append("⚠️ Score élevé mais tendance non confirmée (RSI/MACD/SMA pas assez alignés) → signal rétrogradé")
    elif score >= 58:
        if indicateurs_tendance_haussiers >= 2:
            signal = "📈 ACHAT"
        else:
            signal = "⚖️ ATTENDRE"
            reasons.append("⚠️ Score favorable mais tendance non confirmée (RSI/MACD/SMA pas assez alignés) → signal rétrogradé")
    elif score >= 42:
        signal = "⚖️ ATTENDRE"
    elif score >= 30:
        signal = "📉 VENTE"
    else:
        signal = "🔻 VENTE FORTE"

    # --- Confiance réelle : force du consensus (hors votes neutres) ---
    if total_weight == 0:
        confidence = 0
    else:
        consensus = max(bullish_weight, bearish_weight)
        confidence = round((consensus / total_weight) * 100)
    if not volume_confirme and total_weight > 0:
        confidence = max(0, confidence - 10)

    macd_trend = "Haussier" if macd_bullish else "Baissier"

    return {
        "score": score,
        "signal": signal,
        "confidence": confidence,
        "reasons": reasons,
        "rsi": round(row['rsi'], 1),
        "macd_trend": macd_trend,
        "bullish_weight": bullish_weight,
        "bearish_weight": bearish_weight,
        "total_weight": total_weight,
    }


def analyse_crypto_v2(coin):
    """
    Analyse complète multi-indicateurs pour une crypto en direct.
    Retourne un dict : coin, score, signal, confiance, raisons, rsi,
    macd_trend, volatilite_pct
    """
    df = get_market_data(coin, days=60)
    df = calculate_indicators(df)
    latest = df.iloc[-1]

    resultat = calculer_score(latest)
    resultat["coin"] = coin
    resultat["volatilite_pct"] = (
        round(latest['volatilite_pct'], 2) if pd.notna(latest['volatilite_pct']) else None
    )

    return resultat
