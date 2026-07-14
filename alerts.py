"""
alerts.py — Alertes pour FuturIA Crypto

Détecte les signaux forts (ACHAT FORT / VENTE FORTE) et déclenche une
alerte : notification Android si possible, sinon affichage console bien
visible + enregistrement dans un historique (alerts.db).

⚠️ Limite Pydroid3 : contrairement à une vraie app Android compilée,
Pydroid3 n'a pas toujours accès à l'API de notifications système. On tente
via la librairie `plyer`, et si ça échoue, on bascule automatiquement sur
une alerte console bien visible (qui fonctionne toujours).
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager


DB_PATH = "alerts.db"

# Signaux considérés comme "forts" -> déclenchent une alerte
SIGNAUX_FORTS = ["ACHAT FORT", "VENTE FORTE"]


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alertes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                crypto TEXT NOT NULL,
                signal TEXT NOT NULL,
                prix REAL NOT NULL,
                score REAL,
                confidence REAL
            )
        """)


_init_db()


def est_signal_fort(signal: str) -> bool:
    signal_maj = signal.upper()
    return any(s in signal_maj for s in SIGNAUX_FORTS)


def _notifier_android(titre: str, message: str) -> bool:
    """
    Tente d'envoyer une vraie notification Android via plyer.
    Retourne True si ça a fonctionné, False sinon (fallback console).
    """
    try:
        from plyer import notification
        notification.notify(title=titre, message=message, timeout=10)
        return True
    except Exception:
        return False


def _alerte_console(titre: str, message: str):
    """Alerte console bien visible, utilisée si la notification Android échoue."""
    print("\n" + "🔔" * 20)
    print(f"🚨 {titre}")
    print(message)
    print("🔔" * 20 + "\n")


def _enregistrer(crypto: str, signal: str, prix: float, score: float, confidence: float):
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO alertes (date, crypto, signal, prix, score, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (datetime.now().strftime("%d/%m/%Y %H:%M"), crypto, signal, prix, score, confidence),
        )


def verifier_alerte(coin: str, prix: float, signal: str, score: float, confidence: float) -> bool:
    """
    Fonction principale à appeler après chaque analyse.
    Si le signal est fort, déclenche une alerte (notification ou console) et
    l'enregistre dans l'historique. Retourne True si une alerte a été déclenchée.
    """
    if not est_signal_fort(signal):
        return False

    titre = f"⚡ Signal fort détecté : {coin}"
    message = (
        f"{signal} sur {coin}\n"
        f"Prix : {prix:,.2f} $\n"
        f"Score IA : {score}/100 | Confiance : {confidence}%"
    ).replace(",", " ")

    envoye = _notifier_android(titre, message)
    if not envoye:
        _alerte_console(titre, message)

    _enregistrer(coin, signal, prix, score, confidence)
    return True


def historique_alertes(limite: int = 50) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alertes ORDER BY id DESC LIMIT ?", (limite,)
        ).fetchall()
        return [dict(r) for r in rows]


# ----------------------------------------------------------------------
# Test rapide
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Test 1 : signal fort (doit déclencher une alerte)")
    declenchee = verifier_alerte("BTCUSDT", 62000, "🔥 ACHAT FORT", 78, 90)
    print(f"Alerte déclenchée : {declenchee}\n")

    print("Test 2 : signal faible (ne doit rien déclencher)")
    declenchee = verifier_alerte("ETHUSDT", 3400, "⚖️ ATTENDRE", 48, 40)
    print(f"Alerte déclenchée : {declenchee}\n")

    print("Historique des alertes enregistrées :")
    for a in historique_alertes():
        print(a)
