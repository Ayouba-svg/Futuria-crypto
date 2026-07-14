"""
journal.py — Journal d'analyse pour FuturIA Crypto

Ce module enregistre chaque analyse effectuée par l'IA, permet de relire
l'historique, et calcule des statistiques de performance.

Stockage : SQLite (fichier local journal.db), ce qui permettra plus tard
d'entraîner un modèle de machine learning directement sur ces données.
"""

import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional


DB_PATH = "journal.db"


@dataclass
class Analyse:
    """Représente une ligne du journal d'analyse."""
    id: Optional[int]
    date: str
    crypto: str
    prix: float
    rsi: float
    macd: str
    score_ia: float
    signal: str
    raison: str
    resultat_24h: Optional[str] = None      # "GAIN" / "PERTE" / None
    prix_24h: Optional[float] = None
    precision_ia: Optional[float] = None     # en %


class Journal:
    """Gère l'enregistrement, la lecture et les statistiques des analyses."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    crypto TEXT NOT NULL,
                    prix REAL NOT NULL,
                    rsi REAL,
                    macd TEXT,
                    score_ia REAL,
                    signal TEXT NOT NULL,
                    raison TEXT,
                    resultat_24h TEXT,
                    prix_24h REAL,
                    precision_ia REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crypto ON analyses(crypto)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON analyses(date)")

    def enregistrer(
        self,
        crypto: str,
        prix: float,
        rsi: float,
        macd: str,
        score_ia: float,
        signal: str,
        raison: str,
        date: Optional[str] = None,
    ) -> int:
        """Enregistre une nouvelle analyse dans le journal. Retourne l'id créé."""
        date = date or datetime.now().strftime("%d/%m/%Y %H:%M")
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO analyses
                    (date, crypto, prix, rsi, macd, score_ia, signal, raison)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (date, crypto, prix, rsi, macd, score_ia, signal, raison),
            )
            return cur.lastrowid

    def mettre_a_jour_resultat(self, analyse_id: int, prix_24h: float):
        """Calcule GAIN/PERTE et la précision à partir du prix constaté 24h plus tard."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT prix, signal FROM analyses WHERE id = ?", (analyse_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Analyse id={analyse_id} introuvable")

            prix_initial, signal = row["prix"], row["signal"]
            variation = (prix_24h - prix_initial) / prix_initial * 100

            if "ACHAT" in signal.upper():
                resultat = "GAIN" if variation > 0 else "PERTE"
                precision = abs(variation)
            elif "VENTE" in signal.upper():
                resultat = "GAIN" if variation < 0 else "PERTE"
                precision = abs(variation)
            else:
                resultat = "NEUTRE"
                precision = 0.0

            conn.execute(
                """
                UPDATE analyses
                SET resultat_24h = ?, prix_24h = ?, precision_ia = ?
                WHERE id = ?
                """,
                (resultat, prix_24h, round(precision, 2), analyse_id),
            )

    def analyses_en_attente_de_resultat(self, heures: int = 24) -> list:
        """Retourne les analyses vieilles d'au moins `heures` et pas encore évaluées."""
        seuil = (datetime.now() - timedelta(hours=heures)).strftime("%d/%m/%Y %H:%M")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM analyses
                WHERE resultat_24h IS NULL AND date <= ?
                ORDER BY date ASC
                """,
                (seuil,),
            ).fetchall()
            return [self._row_to_analyse(r) for r in rows]

    def historique(self, crypto: Optional[str] = None, limite: int = 100) -> list:
        """Relit l'historique des analyses, du plus récent au plus ancien."""
        with self._connect() as conn:
            if crypto:
                rows = conn.execute(
                    "SELECT * FROM analyses WHERE crypto = ? ORDER BY id DESC LIMIT ?",
                    (crypto, limite),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limite,)
                ).fetchall()
            return [self._row_to_analyse(r) for r in rows]

    def statistiques(self, crypto: Optional[str] = None) -> dict:
        """Calcule les statistiques de performance (sur analyses déjà évaluées à 24h)."""
        with self._connect() as conn:
            base_query = "SELECT * FROM analyses WHERE resultat_24h IS NOT NULL"
            params = ()
            if crypto:
                base_query += " AND crypto = ?"
                params = (crypto,)
            rows = conn.execute(base_query, params).fetchall()

        total = len(rows)
        if total == 0:
            return {
                "total_analyses_evaluees": 0,
                "taux_reussite": None,
                "gains": 0,
                "pertes": 0,
                "neutres": 0,
                "precision_moyenne": None,
            }

        gains = sum(1 for r in rows if r["resultat_24h"] == "GAIN")
        pertes = sum(1 for r in rows if r["resultat_24h"] == "PERTE")
        neutres = sum(1 for r in rows if r["resultat_24h"] == "NEUTRE")
        evaluables = gains + pertes
        taux_reussite = round(gains / evaluables * 100, 2) if evaluables else None

        precisions = [r["precision_ia"] for r in rows if r["precision_ia"] is not None]
        precision_moyenne = round(sum(precisions) / len(precisions), 2) if precisions else None

        return {
            "total_analyses_evaluees": total,
            "taux_reussite": taux_reussite,
            "gains": gains,
            "pertes": pertes,
            "neutres": neutres,
            "precision_moyenne": precision_moyenne,
        }

    def nombre_total_analyses(self) -> int:
        """Utile pour savoir quand on atteint le seuil (ex: 1000) pour entraîner un modèle ML."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM analyses").fetchone()
            return row["n"]

    def exporter_csv(self, chemin: str = "journal_export.csv"):
        import csv
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM analyses ORDER BY id ASC").fetchall()
        if not rows:
            return
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(rows[0].keys())
            for r in rows:
                writer.writerow(tuple(r))

    @staticmethod
    def _row_to_analyse(row):
        return Analyse(
            id=row["id"],
            date=row["date"],
            crypto=row["crypto"],
            prix=row["prix"],
            rsi=row["rsi"],
            macd=row["macd"],
            score_ia=row["score_ia"],
            signal=row["signal"],
            raison=row["raison"],
            resultat_24h=row["resultat_24h"],
            prix_24h=row["prix_24h"],
            precision_ia=row["precision_ia"],
        )


def formater_analyse(a: Analyse) -> str:
    """Formate une analyse pour affichage."""
    emoji_signal = {"ACHAT": "🟢", "VENTE": "🔴", "ATTENDRE": "🟡"}
    emoji = next((v for k, v in emoji_signal.items() if k in a.signal.upper()), "")
    lignes = [
        f"Date : {a.date}",
        f"Crypto : {a.crypto}",
        f"Prix : {a.prix:,.0f} $".replace(",", " "),
        f"RSI : {a.rsi}",
        f"MACD : {a.macd}",
        f"Score IA : {a.score_ia}",
        f"Signal : {emoji} {a.signal}",
        f"Raison : {a.raison}",
    ]
    if a.resultat_24h:
        lignes.append(f"Résultat 24h : {a.resultat_24h} (précision {a.precision_ia}%)")
    return "\n".join(lignes)