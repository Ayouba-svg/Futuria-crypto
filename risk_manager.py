"""
risk_manager.py — Gestion du risque pour FuturIA Crypto

Calcule, pour chaque signal, un stop-loss, un take-profit et un niveau de
risque, à partir du prix et de la confiance de l'IA dans son analyse.

Version 1 : basée sur des pourcentages fixes (pas encore sur la volatilité
réelle du marché type ATR). On pourra affiner plus tard avec un indicateur
de volatilité dans indicators.py.
"""

from dataclasses import dataclass
from typing import Optional


# --- Paramètres par défaut (modifiables) ---
STOP_LOSS_PCT = 3.0          # distance du stop-loss par rapport au prix d'entrée
RATIO_RISQUE_RENDEMENT = 2.0  # take-profit = stop-loss x ce ratio (ex: 1:2)

# % du solde à risquer selon le niveau de risque du trade
RISQUE_PAR_NIVEAU = {
    "Faible": 2.0,
    "Moyen": 1.0,
    "Élevé": 0.5,
}


@dataclass
class EvaluationRisque:
    crypto: str
    signal: str
    prix_entree: float
    stop_loss: float
    take_profit: float
    niveau_risque: str
    ratio_risque_rendement: float
    pct_solde_recommande: float


def _direction(signal: str) -> Optional[str]:
    """Retourne 'ACHAT', 'VENTE' ou None (ATTENDRE) selon le signal."""
    signal_maj = signal.upper()
    if "ACHAT" in signal_maj:
        return "ACHAT"
    if "VENTE" in signal_maj:
        return "VENTE"
    return None


def niveau_risque(confidence: float) -> str:
    """
    Détermine le niveau de risque du trade à partir de la confiance de l'IA
    (le pourcentage d'indicateurs qui sont d'accord entre eux).
    """
    if confidence >= 80:
        return "Faible"
    elif confidence >= 60:
        return "Moyen"
    else:
        return "Élevé"


def calculer_niveaux(prix: float, signal: str, stop_loss_pct: float = STOP_LOSS_PCT,
                      ratio: float = RATIO_RISQUE_RENDEMENT) -> Optional[tuple]:
    """Calcule (stop_loss, take_profit) selon la direction du signal."""
    direction = _direction(signal)
    if direction is None:
        return None

    take_profit_pct = stop_loss_pct * ratio

    if direction == "ACHAT":
        stop_loss = prix * (1 - stop_loss_pct / 100)
        take_profit = prix * (1 + take_profit_pct / 100)
    else:  # VENTE
        stop_loss = prix * (1 + stop_loss_pct / 100)
        take_profit = prix * (1 - take_profit_pct / 100)

    return round(stop_loss, 6), round(take_profit, 6)


def evaluer(coin: str, prix: float, signal: str, confidence: float) -> Optional[EvaluationRisque]:
    """
    Fonction principale : calcule stop-loss, take-profit, niveau de risque et
    la part du solde à risquer, pour un signal donné.
    Retourne None si le signal est ATTENDRE (rien à risquer).
    """
    niveaux = calculer_niveaux(prix, signal)
    if niveaux is None:
        return None

    stop_loss, take_profit = niveaux
    risque = niveau_risque(confidence)
    pct_solde = RISQUE_PAR_NIVEAU[risque]

    return EvaluationRisque(
        crypto=coin,
        signal=signal,
        prix_entree=prix,
        stop_loss=stop_loss,
        take_profit=take_profit,
        niveau_risque=risque,
        ratio_risque_rendement=RATIO_RISQUE_RENDEMENT,
        pct_solde_recommande=pct_solde,
    )


def formater_evaluation(e: EvaluationRisque) -> str:
    """Formate une évaluation de risque pour affichage."""
    emoji_risque = {"Faible": "🟢", "Moyen": "🟡", "Élevé": "🔴"}
    emoji = emoji_risque.get(e.niveau_risque, "")
    return (
        f"{e.crypto} | Signal : {e.signal}\n"
        f"Prix d'entrée : {e.prix_entree:,.2f} $\n"
        f"Stop-loss : {e.stop_loss:,.2f} $\n"
        f"Take-profit : {e.take_profit:,.2f} $\n"
        f"Ratio risque/rendement : 1:{e.ratio_risque_rendement:.0f}\n"
        f"Niveau de risque : {emoji} {e.niveau_risque}\n"
        f"Part du solde recommandée : {e.pct_solde_recommande}%"
    ).replace(",", " ")


# ----------------------------------------------------------------------
# Test rapide
# ----------------------------------------------------------------------
if __name__ == "__main__":
    cas_test = [
        ("BTCUSDT", 62000, "🔥 ACHAT FORT", 90),
        ("ETHUSDT", 3400, "📈 ACHAT", 65),
        ("SOLUSDT", 145, "🔻 VENTE FORTE", 55),
        ("ADAUSDT", 0.45, "⚖️ ATTENDRE", 40),
    ]

    for coin, prix, signal, confidence in cas_test:
        evaluation = evaluer(coin, prix, signal, confidence)
        print("-" * 50)
        if evaluation:
            print(formater_evaluation(evaluation))
        else:
            print(f"{coin} | Signal : {signal} → aucune action de risque nécessaire")
