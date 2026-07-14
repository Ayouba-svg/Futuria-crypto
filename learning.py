"""
learning.py — Analyse du journal pour FuturIA Crypto

RÈGLE STRICTE : ce module n'écrit jamais dans ai_engine.py.
Il lit journal.db, met à jour les résultats à 24h, puis produit un
rapport texte avec des recommandations. C'est l'humain qui décide.
"""

import time
from journal import Journal
from data import get_crypto


def mettre_a_jour_resultats_en_attente(journal):
    """Pour chaque analyse vieille de 24h+ sans résultat, récupère le prix actuel et l'enregistre.
    Le prix de chaque crypto n'est demandé qu'une seule fois (mis en cache), même si plusieurs
    analyses en attente concernent la même crypto."""
    en_attente = journal.analyses_en_attente_de_resultat(heures=24)
    if not en_attente:
        print("Aucune analyse en attente de résultat (rien de plus vieux que 24h à évaluer).")
        return 0

    prix_cache = {}
    maj = 0

    for analyse in en_attente:
        crypto = analyse.crypto

        if crypto not in prix_cache:
            try:
                prix_actuel, _ = get_crypto(crypto)
                prix_cache[crypto] = prix_actuel
                time.sleep(3)  # pause entre chaque NOUVELLE crypto interrogée
            except Exception as e:
                print(f"⚠️ Impossible de récupérer le prix de {crypto} : {e}")
                prix_cache[crypto] = None

        prix_actuel = prix_cache[crypto]
        if prix_actuel is None:
            continue

        try:
            journal.mettre_a_jour_resultat(analyse.id, prix_actuel)
            maj += 1
        except Exception as e:
            print(f"⚠️ Impossible de mettre à jour {crypto} (id={analyse.id}) : {e}")

    print(f"✅ {maj} analyse(s) mise(s) à jour avec leur résultat 24h.\n")
    return maj


def analyser_performance_par_signal(journal):
    """Compare le taux de réussite par type de signal (ACHAT vs VENTE)."""
    historique = journal.historique(limite=1000)
    evalues = [a for a in historique if a.resultat_24h is not None]

    if not evalues:
        return {}

    stats_par_signal = {}
    for a in evalues:
        cle = "ACHAT" if "ACHAT" in a.signal.upper() else ("VENTE" if "VENTE" in a.signal.upper() else "ATTENDRE")
        stats_par_signal.setdefault(cle, {"gains": 0, "pertes": 0, "neutres": 0})
        if a.resultat_24h == "GAIN":
            stats_par_signal[cle]["gains"] += 1
        elif a.resultat_24h == "PERTE":
            stats_par_signal[cle]["pertes"] += 1
        else:
            stats_par_signal[cle]["neutres"] += 1

    return stats_par_signal


def analyser_performance_par_crypto(journal):
    """Compare le taux de réussite par crypto."""
    historique = journal.historique(limite=1000)
    evalues = [a for a in historique if a.resultat_24h is not None]

    if not evalues:
        return {}

    stats_par_crypto = {}
    for a in evalues:
        stats_par_crypto.setdefault(a.crypto, {"gains": 0, "pertes": 0})
        if a.resultat_24h == "GAIN":
            stats_par_crypto[a.crypto]["gains"] += 1
        elif a.resultat_24h == "PERTE":
            stats_par_crypto[a.crypto]["pertes"] += 1

    return stats_par_crypto


def generer_recommandations(stats_signal, stats_crypto, total_evalue):
    """Génère des recommandations en texte clair, à titre indicatif uniquement."""
    recommandations = []

    if total_evalue < 20:
        recommandations.append(
            f"⚠️ Seulement {total_evalue} analyse(s) évaluée(s) — trop peu pour tirer des "
            f"conclusions fiables. Continue à faire tourner le programme régulièrement."
        )
        return recommandations

    for signal, stats in stats_signal.items():
        total = stats["gains"] + stats["pertes"]
        if total == 0:
            continue
        taux = round(stats["gains"] / total * 100, 1)
        if taux < 40:
            recommandations.append(
                f"🔴 Le signal '{signal}' ne réussit qu'à {taux}% ({stats['gains']}/{total}). "
                f"Ce type de signal semble peu fiable actuellement, à surveiller de près."
            )
        elif taux > 65:
            recommandations.append(
                f"🟢 Le signal '{signal}' réussit à {taux}% ({stats['gains']}/{total}). "
                f"Ce type de signal semble performant en ce moment."
            )

    for crypto, stats in stats_crypto.items():
        total = stats["gains"] + stats["pertes"]
        if total < 5:
            continue
        taux = round(stats["gains"] / total * 100, 1)
        if taux < 40:
            recommandations.append(
                f"🔴 {crypto.upper()} : taux de réussite faible ({taux}%, {stats['gains']}/{total}). "
                f"Envisage de la retirer temporairement de COINS ou de la surveiller davantage."
            )
        elif taux > 65:
            recommandations.append(
                f"🟢 {crypto.upper()} : taux de réussite élevé ({taux}%, {stats['gains']}/{total})."
            )

    if not recommandations:
        recommandations.append("Pas de tendance nette pour l'instant — continue à accumuler des données.")

    return recommandations


def generer_rapport():
    """Fonction principale : met à jour les résultats, analyse, et affiche un rapport complet."""
    journal = Journal()

    print("=" * 50)
    print("🧠 RAPPORT D'APPRENTISSAGE - FUTURIA CRYPTO")
    print("=" * 50 + "\n")

    mettre_a_jour_resultats_en_attente(journal)

    stats_globales = journal.statistiques()
    total_evalue = stats_globales["total_analyses_evaluees"]

    print(f"Total d'analyses évaluées : {total_evalue}")
    if total_evalue > 0:
        print(f"Taux de réussite global : {stats_globales['taux_reussite']}%")
        print(f"Précision moyenne : {stats_globales['precision_moyenne']}%")

    print("\n--- Performance par type de signal ---")
    stats_signal = analyser_performance_par_signal(journal)
    for signal, s in stats_signal.items():
        total = s["gains"] + s["pertes"]
        taux = round(s["gains"] / total * 100, 1) if total else None
        print(f"  {signal} : {s['gains']} gains / {s['pertes']} pertes" + (f" ({taux}%)" if taux is not None else ""))

    print("\n--- Performance par crypto ---")
    stats_crypto = analyser_performance_par_crypto(journal)
    for crypto, s in stats_crypto.items():
        total = s["gains"] + s["pertes"]
        taux = round(s["gains"] / total * 100, 1) if total else None
        print(f"  {crypto.upper()} : {s['gains']} gains / {s['pertes']} pertes" + (f" ({taux}%)" if taux is not None else ""))

    print("\n--- 💡 Recommandations (à valider manuellement) ---")
    recommandations = generer_recommandations(stats_signal, stats_crypto, total_evalue)
    for r in recommandations:
        print(f"  • {r}")

    print("\n" + "=" * 50)
    print("Rappel : ce rapport n'a rien modifié automatiquement.")
    print("Les ajustements du moteur IA restent entièrement sous ton contrôle.")
    print("=" * 50)


if __name__ == "__main__":
    generer_rapport()