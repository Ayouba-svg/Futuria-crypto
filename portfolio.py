"""
portfolio.py — Portefeuille virtuel pour FuturIA Crypto

Simule des trades basés sur les signaux de l'IA, sans argent réel.
Permet de mesurer la performance réelle de la stratégie dans le temps.

Stockage : SQLite (fichier local portfolio.db)
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional


DB_PATH = "portfolio.db"
SOLDE_INITIAL = 10000.0   # capital virtuel de départ ($)
TAILLE_POSITION_PCT = 10  # % du solde disponible investi à chaque achat (valeur par défaut)


@dataclass
class Position:
    id: int
    crypto: str
    quantite: float
    prix_entree: float
    date_entree: str
    montant_investi: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class Transaction:
    id: int
    crypto: str
    quantite: float
    prix_entree: float
    prix_sortie: float
    date_entree: str
    date_sortie: str
    gain_perte: float
    gain_perte_pct: float


class Portfolio:
    """Gère le solde, les positions ouvertes et l'historique des trades virtuels."""

    def __init__(self, db_path: str = DB_PATH, solde_initial: float = SOLDE_INITIAL):
        self.db_path = db_path
        self._init_db(solde_initial)

    # ------------------------------------------------------------------
    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self, solde_initial: float):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS etat (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    solde REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crypto TEXT NOT NULL,
                    quantite REAL NOT NULL,
                    prix_entree REAL NOT NULL,
                    date_entree TEXT NOT NULL,
                    montant_investi REAL NOT NULL
                )
            """)
            colonnes = [c["name"] for c in conn.execute("PRAGMA table_info(positions)").fetchall()]
            if "stop_loss" not in colonnes:
                conn.execute("ALTER TABLE positions ADD COLUMN stop_loss REAL")
            if "take_profit" not in colonnes:
                conn.execute("ALTER TABLE positions ADD COLUMN take_profit REAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    crypto TEXT NOT NULL,
                    quantite REAL NOT NULL,
                    prix_entree REAL NOT NULL,
                    prix_sortie REAL NOT NULL,
                    date_entree TEXT NOT NULL,
                    date_sortie TEXT NOT NULL,
                    gain_perte REAL NOT NULL,
                    gain_perte_pct REAL NOT NULL
                )
            """)
            existe = conn.execute("SELECT 1 FROM etat WHERE id = 1").fetchone()
            if not existe:
                conn.execute("INSERT INTO etat (id, solde) VALUES (1, ?)", (solde_initial,))

    # ------------------------------------------------------------------
    # Solde et positions
    # ------------------------------------------------------------------
    def solde(self) -> float:
        with self._connect() as conn:
            row = conn.execute("SELECT solde FROM etat WHERE id = 1").fetchone()
            return row["solde"]

    def _modifier_solde(self, conn, delta: float):
        conn.execute("UPDATE etat SET solde = solde + ? WHERE id = 1", (delta,))

    def position_ouverte(self, crypto: str) -> Optional[Position]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM positions WHERE crypto = ?", (crypto,)
            ).fetchone()
            return self._row_to_position(row) if row else None

    def positions_ouvertes(self) -> list:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM positions").fetchall()
            return [self._row_to_position(r) for r in rows]

    # ------------------------------------------------------------------
    # Actions de trading virtuel
    # ------------------------------------------------------------------
    def acheter(self, crypto: str, prix: float, taille_pct: float = TAILLE_POSITION_PCT,
                stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> Optional[Position]:
        """
        Ouvre une position virtuelle si on n'en a pas déjà une sur cette crypto.
        Investit `taille_pct` % du solde disponible.
        """
        if self.position_ouverte(crypto) is not None:
            return None

        with self._connect() as conn:
            solde_actuel = conn.execute("SELECT solde FROM etat WHERE id = 1").fetchone()["solde"]
            montant = solde_actuel * (taille_pct / 100)

            if montant <= 0 or montant > solde_actuel:
                return None

            quantite = montant / prix
            date_entree = datetime.now().strftime("%d/%m/%Y %H:%M")

            cur = conn.execute(
                """
                INSERT INTO positions
                    (crypto, quantite, prix_entree, date_entree, montant_investi, stop_loss, take_profit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (crypto, quantite, prix, date_entree, montant, stop_loss, take_profit),
            )
            self._modifier_solde(conn, -montant)

            return Position(
                id=cur.lastrowid,
                crypto=crypto,
                quantite=quantite,
                prix_entree=prix,
                date_entree=date_entree,
                montant_investi=montant,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

    def vendre(self, crypto: str, prix: float) -> Optional[Transaction]:
        """Ferme la position ouverte sur cette crypto au prix donné, si elle existe."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM positions WHERE crypto = ?", (crypto,)).fetchone()
            if row is None:
                return None

            pos = self._row_to_position(row)
            valeur_sortie = pos.quantite * prix
            gain_perte = valeur_sortie - pos.montant_investi
            gain_perte_pct = round((gain_perte / pos.montant_investi) * 100, 2)
            date_sortie = datetime.now().strftime("%d/%m/%Y %H:%M")

            conn.execute("DELETE FROM positions WHERE id = ?", (pos.id,))
            self._modifier_solde(conn, valeur_sortie)

            cur = conn.execute(
                """
                INSERT INTO transactions
                    (crypto, quantite, prix_entree, prix_sortie, date_entree, date_sortie,
                     gain_perte, gain_perte_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pos.crypto, pos.quantite, pos.prix_entree, prix, pos.date_entree,
                 date_sortie, gain_perte, gain_perte_pct),
            )

            return Transaction(
                id=cur.lastrowid,
                crypto=pos.crypto,
                quantite=pos.quantite,
                prix_entree=pos.prix_entree,
                prix_sortie=prix,
                date_entree=pos.date_entree,
                date_sortie=date_sortie,
                gain_perte=round(gain_perte, 2),
                gain_perte_pct=gain_perte_pct,
            )

    # ------------------------------------------------------------------
    # Traitement automatique d'un signal (à appeler depuis main.py)
    # ------------------------------------------------------------------
    def traiter_signal(self, crypto: str, prix: float, signal: str,
                        stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
                        taille_pct: float = TAILLE_POSITION_PCT) -> Optional[dict]:
        """
        Réagit automatiquement à un signal de l'IA :
        - ACHAT / ACHAT FORT → ouvre une position (si aucune en cours), avec
          stop_loss/take_profit et taille_pct si fournis (venant de risk_manager.py)
        - VENTE / VENTE FORTE → ferme la position (si une est ouverte)
        - ATTENDRE → ne fait rien
        """
        signal_maj = signal.upper()

        if "ACHAT" in signal_maj:
            pos = self.acheter(crypto, prix, taille_pct=taille_pct, stop_loss=stop_loss, take_profit=take_profit)
            if pos:
                return {"action": "ACHAT", "crypto": crypto, "prix": prix, "montant": pos.montant_investi}

        elif "VENTE" in signal_maj:
            tx = self.vendre(crypto, prix)
            if tx:
                return {
                    "action": "VENTE",
                    "crypto": crypto,
                    "prix": prix,
                    "gain_perte": tx.gain_perte,
                    "gain_perte_pct": tx.gain_perte_pct,
                }

        return None

    # ------------------------------------------------------------------
    # Vérification automatique du stop-loss / take-profit
    # ------------------------------------------------------------------
    def verifier_stop_take(self, crypto: str, prix_actuel: float) -> Optional[dict]:
        """
        Vérifie si la position ouverte sur `crypto` a atteint son stop-loss ou
        son take-profit au prix actuel. Si oui, ferme la position automatiquement.
        """
        pos = self.position_ouverte(crypto)
        if pos is None or (pos.stop_loss is None and pos.take_profit is None):
            return None

        est_position_achat = pos.stop_loss is not None and pos.stop_loss < pos.prix_entree

        declenche = None
        if est_position_achat:
            if pos.take_profit is not None and prix_actuel >= pos.take_profit:
                declenche = "TAKE-PROFIT"
            elif pos.stop_loss is not None and prix_actuel <= pos.stop_loss:
                declenche = "STOP-LOSS"
        else:
            if pos.take_profit is not None and prix_actuel <= pos.take_profit:
                declenche = "TAKE-PROFIT"
            elif pos.stop_loss is not None and prix_actuel >= pos.stop_loss:
                declenche = "STOP-LOSS"

        if declenche is None:
            return None

        tx = self.vendre(crypto, prix_actuel)
        if tx is None:
            return None

        return {
            "action": f"FERMETURE AUTO ({declenche})",
            "crypto": crypto,
            "prix": prix_actuel,
            "gain_perte": tx.gain_perte,
            "gain_perte_pct": tx.gain_perte_pct,
        }

    # ------------------------------------------------------------------
    # Statistiques de performance
    # ------------------------------------------------------------------
    def valeur_totale(self, prix_actuels: dict) -> float:
        """Valeur totale = solde disponible + valeur des positions ouvertes valorisées au prix actuel."""
        total = self.solde()
        for pos in self.positions_ouvertes():
            prix_actuel = prix_actuels.get(pos.crypto)
            if prix_actuel:
                total += pos.quantite * prix_actuel
            else:
                total += pos.montant_investi
        return round(total, 2)

    def statistiques(self, prix_actuels: Optional[dict] = None) -> dict:
        """
        Calcule les statistiques de performance.
        Si `prix_actuels` est fourni, le rendement se base sur la valeur totale
        réelle (solde + positions ouvertes valorisées au marché). Sinon, il se
        base uniquement sur le solde disponible (comportement historique).
        """
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM transactions").fetchall()

        nb_trades = len(rows)

        if prix_actuels is not None:
            valeur_reference = self.valeur_totale(prix_actuels)
        else:
            valeur_reference = self.solde()

        rendement_pct = round((valeur_reference - SOLDE_INITIAL) / SOLDE_INITIAL * 100, 2)

        if nb_trades == 0:
            return {
                "solde_disponible": self.solde(),
                "valeur_totale": valeur_reference if prix_actuels is not None else None,
                "nb_trades_clotures": 0,
                "gains": 0,
                "pertes": 0,
                "taux_reussite": None,
                "profit_total": 0.0,
                "rendement_pct": rendement_pct,
            }

        gains = sum(1 for r in rows if r["gain_perte"] > 0)
        pertes = sum(1 for r in rows if r["gain_perte"] <= 0)
        profit_total = sum(r["gain_perte"] for r in rows)
        taux_reussite = round(gains / nb_trades * 100, 2)

        return {
            "solde_disponible": self.solde(),
            "valeur_totale": valeur_reference if prix_actuels is not None else None,
            "nb_trades_clotures": nb_trades,
            "gains": gains,
            "pertes": pertes,
            "taux_reussite": taux_reussite,
            "profit_total": round(profit_total, 2),
            "rendement_pct": rendement_pct,
        }

    def historique_transactions(self, limite: int = 50) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
            return [self._row_to_transaction(r) for r in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_position(row) -> Position:
        return Position(
            id=row["id"],
            crypto=row["crypto"],
            quantite=row["quantite"],
            prix_entree=row["prix_entree"],
            date_entree=row["date_entree"],
            montant_investi=row["montant_investi"],
            stop_loss=row["stop_loss"] if "stop_loss" in row.keys() else None,
            take_profit=row["take_profit"] if "take_profit" in row.keys() else None,
        )

    @staticmethod
    def _row_to_transaction(row) -> Transaction:
        return Transaction(
            id=row["id"],
            crypto=row["crypto"],
            quantite=row["quantite"],
            prix_entree=row["prix_entree"],
            prix_sortie=row["prix_sortie"],
            date_entree=row["date_entree"],
            date_sortie=row["date_sortie"],
            gain_perte=row["gain_perte"],
            gain_perte_pct=row["gain_perte_pct"],
        )


# ----------------------------------------------------------------------
# Test rapide
# ----------------------------------------------------------------------
if __name__ == "__main__":
    p = Portfolio(db_path="test_portfolio.db")

    print(f"Solde initial : {p.solde()} $")

    action = p.traiter_signal("BTCUSDT", 62000, "🔥 ACHAT FORT", stop_loss=60140, take_profit=65720, taille_pct=2.0)
    print("Action :", action)
    print(f"Solde après achat : {p.solde()} $")

    auto = p.verifier_stop_take("BTCUSDT", 63000)
    print("Vérification (prix normal) :", auto)

    auto = p.verifier_stop_take("BTCUSDT", 66000)
    print("Vérification (take-profit atteint) :", auto)
    print(f"Solde après fermeture auto : {p.solde()} $")

    print("\nStatistiques (solde seul) :", p.statistiques())
    print("Statistiques (valeur totale) :", p.statistiques(prix_actuels={"BTCUSDT": 66000}))