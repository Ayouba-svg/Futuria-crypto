import time
from data import get_crypto
from ai_engine import analyse_crypto_v2
from interface import display_results_v2
from config import COINS
from journal import Journal
from portfolio import Portfolio
from risk_manager import evaluer, formater_evaluation
from alerts import verifier_alerte
from charts import generate_chart

journal = Journal()
portfolio = Portfolio()


def main():
    prix_actuels = {}

    for coin in COINS:
        try:
            price, change = get_crypto(coin)
            prix_actuels[coin] = price

            fermeture_auto = portfolio.verifier_stop_take(coin, price)
            if fermeture_auto:
                print(f"⚡ {fermeture_auto['action']} sur {coin} à {price} $ "
                      f"→ {fermeture_auto['gain_perte']} $ ({fermeture_auto['gain_perte_pct']}%)\n")

            result = analyse_crypto_v2(coin)
            display_results_v2(result, price, change)

            chart_path = generate_chart(coin)
            print(f"📊 Graphique sauvegardé : {chart_path}\n")

            journal.enregistrer(
                crypto=result["coin"],
                prix=price,
                rsi=result["rsi"],
                macd=result["macd_trend"],
                score_ia=result["score"],
                signal=result["signal"],
                raison=" + ".join(result["reasons"])
            )

            risque = evaluer(result["coin"], price, result["signal"], result["confidence"])
            if risque:
                print(formater_evaluation(risque))
                print()

            stop_loss = risque.stop_loss if risque else None
            take_profit = risque.take_profit if risque else None
            taille_pct = risque.pct_solde_recommande if risque else 10

            action = portfolio.traiter_signal(
                result["coin"], price, result["signal"],
                stop_loss=stop_loss, take_profit=take_profit, taille_pct=taille_pct
            )
            if action:
                print(f"💼 Portefeuille : {action}\n")

            verifier_alerte(result["coin"], price, result["signal"], result["score"], result["confidence"])

        except Exception as e:
            print(f"❌ Erreur sur {coin}, on passe à la suivante : {e}\n")

        time.sleep(5)

    afficher_statistiques(prix_actuels)


def afficher_statistiques(prix_actuels=None):
    stats_journal = journal.statistiques()
    total = journal.nombre_total_analyses()
    stats_portfolio = portfolio.statistiques(prix_actuels=prix_actuels)

    print("\n" + "=" * 40)
    print("📊 STATISTIQUES DU JOURNAL")
    print("=" * 40)
    print(f"Total analyses enregistrées : {total}")
    if stats_journal["total_analyses_evaluees"] == 0:
        print("Pas encore assez de données évaluées (résultats à 24h manquants).")
    else:
        print(f"Analyses évaluées (24h) : {stats_journal['total_analyses_evaluees']}")
        print(f"Gains : {stats_journal['gains']} | Pertes : {stats_journal['pertes']} | Neutres : {stats_journal['neutres']}")
        print(f"Taux de réussite : {stats_journal['taux_reussite']}%")
        print(f"Précision moyenne : {stats_journal['precision_moyenne']}%")
    print("=" * 40)

    print("\n" + "=" * 40)
    print("💼 STATISTIQUES DU PORTEFEUILLE VIRTUEL")
    print("=" * 40)
    print(f"Solde disponible : {stats_portfolio['solde_disponible']:.2f} $")
    if stats_portfolio.get("valeur_totale") is not None:
        print(f"Valeur totale (solde + positions) : {stats_portfolio['valeur_totale']:.2f} $")
    print(f"Trades clôturés : {stats_portfolio['nb_trades_clotures']}")
    if stats_portfolio["nb_trades_clotures"] > 0:
        print(f"Gains : {stats_portfolio['gains']} | Pertes : {stats_portfolio['pertes']}")
        print(f"Taux de réussite : {stats_portfolio['taux_reussite']}%")
        print(f"Profit total : {stats_portfolio['profit_total']:.2f} $")
    print(f"Rendement global : {stats_portfolio['rendement_pct']}%")
    print("=" * 40)


if __name__ == "__main__":
    main()