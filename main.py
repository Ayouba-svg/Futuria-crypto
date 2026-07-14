import re
import os
import time
import traceback

try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.spinner import Spinner
    from kivy.uix.image import Image
    from kivy.uix.screenmanager import ScreenManager, Screen
    from kivy.core.window import Window
    from kivy.clock import Clock
    import threading

    from config import COINS
    from data import get_crypto
    from ai_engine import analyse_crypto_v2
    from charts import generate_chart
    from portfolio import Portfolio
    from journal import Journal
    from risk_manager import evaluer
    from alerts import verifier_alerte, historique_alertes

    Window.clearcolor = (0.05, 0.05, 0.05, 1)

    MOTIF_EMOJI = re.compile(
        "["
        "\U0001F300-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U0001F1E6-\U0001F1FF"
        "\U0000FE00-\U0000FE0F"
        "\U0000200D"
        "]+",
        flags=re.UNICODE
    )

    def retirer_emojis(texte: str) -> str:
        texte = texte.replace("→", "->")
        sans_emoji = MOTIF_EMOJI.sub("", texte)
        return re.sub(r"\s+", " ", sans_emoji).strip()

    portfolio = Portfolio()
    journal = Journal()

    # ========================================================
    # ÉCRAN 1 : ANALYSE
    # ========================================================
    class EcranAnalyse(Screen):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            layout = BoxLayout(orientation='vertical', padding=15, spacing=10)

            self.selecteur = Spinner(
                text=COINS[0],
                values=COINS,
                size_hint=(1, None),
                height=50,
                font_size='16sp'
            )
            layout.add_widget(self.selecteur)

            self.zone_resultats = Label(
                text="Choisis une crypto puis appuie sur Analyser,\nou lance 'Analyser tout' pour toutes les cryptos.",
                font_size='15sp',
                size_hint_y=None,
                valign='top',
                halign='left'
            )
            self.zone_resultats.bind(
                width=lambda instance, value: instance.setter('text_size')(instance, (value, None))
            )
            self.zone_resultats.bind(
                texture_size=lambda instance, value: instance.setter('height')(instance, value[1])
            )

            self.image_graphique = Image(
                size_hint=(1, None),
                height=0,
                allow_stretch=True,
                keep_ratio=True
            )

            contenu = BoxLayout(orientation='vertical', size_hint_y=None, spacing=15)
            contenu.bind(minimum_height=contenu.setter('height'))
            contenu.add_widget(self.zone_resultats)
            contenu.add_widget(self.image_graphique)

            scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
            scroll.add_widget(contenu)
            layout.add_widget(scroll)

            boutons = BoxLayout(size_hint=(1, None), height=60, spacing=10)

            self.bouton = Button(text="Analyser", font_size='16sp')
            self.bouton.bind(on_press=self.lancer_analyse)
            boutons.add_widget(self.bouton)

            self.bouton_tout = Button(text="Analyser tout", font_size='16sp')
            self.bouton_tout.bind(on_press=self.lancer_analyse_tout)
            boutons.add_widget(self.bouton_tout)

            layout.add_widget(boutons)

            self.add_widget(layout)

        def lancer_analyse(self, instance):
            self.bouton.disabled = True
            self.bouton_tout.disabled = True
            self.zone_resultats.text = "Analyse en cours..."
            self.image_graphique.height = 0
            self.image_graphique.source = ""
            coin = self.selecteur.text
            threading.Thread(target=self._analyser_en_arriere_plan, args=(coin,)).start()

        def _analyser_en_arriere_plan(self, coin):
            try:
                price, change = get_crypto(coin)
                result = analyse_crypto_v2(coin)
                texte = self._formater_resultat(coin, price, change, result)
                chemin_graphique = generate_chart(coin)
            except Exception as e:
                texte = f"Erreur lors de l'analyse : {e}"
                chemin_graphique = None

            Clock.schedule_once(lambda dt: self._afficher_resultat(texte, chemin_graphique))

        def _afficher_resultat(self, texte, chemin_graphique):
            self.zone_resultats.text = texte

            if chemin_graphique and os.path.exists(chemin_graphique):
                self.image_graphique.source = chemin_graphique
                self.image_graphique.reload()
                self.image_graphique.height = 400
            else:
                self.image_graphique.height = 0

            self.bouton.disabled = False
            self.bouton_tout.disabled = False

        def _formater_resultat(self, coin, price, change, result):
            signal = retirer_emojis(result['signal'])
            lignes = [
                f"{coin.upper()}",
                f"Prix : {price} $",
                f"Variation 24h : {round(change, 2)}%",
                "",
                f"Score IA : {result['score']}/100",
                f"Confiance : {result['confidence']}%",
                f"Signal : {signal}",
                "",
                "Raisons :",
            ]
            for r in result['reasons']:
                lignes.append(f"  - {retirer_emojis(r)}")
            return "\n".join(lignes)

        def lancer_analyse_tout(self, instance):
            self.bouton.disabled = True
            self.bouton_tout.disabled = True
            self.image_graphique.height = 0
            self.image_graphique.source = ""
            self.zone_resultats.text = "Analyse de toutes les cryptos en cours...\nCela peut prendre 1 à 2 minutes."
            threading.Thread(target=self._analyser_tout_en_arriere_plan).start()

        def _analyser_tout_en_arriere_plan(self):
            blocs = []
            for coin in COINS:
                try:
                    price, change = get_crypto(coin)

                    fermeture = portfolio.verifier_stop_take(coin, price)
                    if fermeture:
                        blocs.append(
                            f"[FERMETURE AUTO] {coin.upper()} -> {fermeture['action']} "
                            f"({fermeture['gain_perte']} $, {fermeture['gain_perte_pct']}%)"
                        )

                    result = analyse_crypto_v2(coin)

                    journal.enregistrer(
                        crypto=result["coin"], prix=price, rsi=result["rsi"],
                        macd=result["macd_trend"], score_ia=result["score"],
                        signal=result["signal"], raison=" + ".join(result["reasons"])
                    )

                    risque = evaluer(result["coin"], price, result["signal"], result["confidence"])
                    stop_loss = risque.stop_loss if risque else None
                    take_profit = risque.take_profit if risque else None
                    taille_pct = risque.pct_solde_recommande if risque else 10

                    action = portfolio.traiter_signal(
                        result["coin"], price, result["signal"],
                        stop_loss=stop_loss, take_profit=take_profit, taille_pct=taille_pct
                    )

                    verifier_alerte(result["coin"], price, result["signal"], result["score"], result["confidence"])

                    bloc = (
                        f"{coin.upper()} : {price} $ ({round(change, 2)}%)\n"
                        f"  Score {result['score']}/100 | Confiance {result['confidence']}%\n"
                        f"  Signal : {retirer_emojis(result['signal'])}"
                    )
                    if action:
                        bloc += f"\n  Portefeuille : {action['action']}"
                    blocs.append(bloc)

                except Exception as e:
                    blocs.append(f"{coin.upper()} : Erreur - {e}")

                time.sleep(5)

            texte_final = "RÉSULTATS - TOUTES LES CRYPTOS\n\n" + "\n\n".join(blocs)
            Clock.schedule_once(lambda dt: self._afficher_resultat_tout(texte_final))

        def _afficher_resultat_tout(self, texte):
            self.zone_resultats.text = texte
            self.bouton.disabled = False
            self.bouton_tout.disabled = False

    # ========================================================
    # ÉCRAN 2 : PORTEFEUILLE
    # ========================================================
    class EcranPortefeuille(Screen):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            layout = BoxLayout(orientation='vertical', padding=15, spacing=10)

            self.zone_texte = Label(
                text="Appuie sur 'Actualiser' pour voir ton portefeuille.",
                font_size='15sp',
                size_hint_y=None,
                valign='top',
                halign='left'
            )
            self.zone_texte.bind(
                width=lambda instance, value: instance.setter('text_size')(instance, (value, None))
            )
            self.zone_texte.bind(
                texture_size=lambda instance, value: instance.setter('height')(instance, value[1])
            )

            scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
            scroll.add_widget(self.zone_texte)
            layout.add_widget(scroll)

            self.bouton = Button(
                text="Actualiser",
                size_hint=(1, None),
                height=60,
                font_size='18sp'
            )
            self.bouton.bind(on_press=self.actualiser)
            layout.add_widget(self.bouton)

            self.add_widget(layout)

        def actualiser(self, instance):
            self.bouton.disabled = True
            self.zone_texte.text = "Chargement..."
            threading.Thread(target=self._charger_en_arriere_plan).start()

        def _charger_en_arriere_plan(self):
            try:
                prix_actuels = {}
                for coin in COINS:
                    try:
                        prix, _ = get_crypto(coin)
                        prix_actuels[coin] = prix
                    except Exception:
                        pass

                stats = portfolio.statistiques(prix_actuels=prix_actuels)
                positions = portfolio.positions_ouvertes()
                texte = self._formater_portefeuille(stats, positions)
            except Exception as e:
                texte = f"Erreur : {e}"

            Clock.schedule_once(lambda dt: self._afficher(texte))

        def _afficher(self, texte):
            self.zone_texte.text = texte
            self.bouton.disabled = False

        def _formater_portefeuille(self, stats, positions):
            lignes = [
                "PORTEFEUILLE VIRTUEL",
                "",
                f"Solde disponible : {stats['solde_disponible']:.2f} $",
            ]
            if stats.get("valeur_totale") is not None:
                lignes.append(f"Valeur totale : {stats['valeur_totale']:.2f} $")
            lignes.append(f"Rendement global : {stats['rendement_pct']}%")
            lignes.append("")
            lignes.append(f"Trades clôturés : {stats['nb_trades_clotures']}")
            if stats["nb_trades_clotures"] > 0:
                lignes.append(f"Gains : {stats['gains']} | Pertes : {stats['pertes']}")
                lignes.append(f"Taux de réussite : {stats['taux_reussite']}%")
                lignes.append(f"Profit total : {stats['profit_total']:.2f} $")

            lignes.append("")
            lignes.append(f"Positions ouvertes ({len(positions)}) :")
            if not positions:
                lignes.append("  Aucune position ouverte actuellement.")
            else:
                for pos in positions:
                    lignes.append(f"  - {pos.crypto.upper()} : {pos.quantite:.4f} unités")
                    lignes.append(f"    Prix d'entrée : {pos.prix_entree:.2f} $ | Investi : {pos.montant_investi:.2f} $")
                    if pos.stop_loss:
                        lignes.append(f"    Stop-loss : {pos.stop_loss:.2f} $")
                    if pos.take_profit:
                        lignes.append(f"    Take-profit : {pos.take_profit:.2f} $")

            return "\n".join(lignes)

    # ========================================================
    # ÉCRAN 3 : ALERTES
    # ========================================================
    class EcranAlertes(Screen):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            layout = BoxLayout(orientation='vertical', padding=15, spacing=10)

            self.zone_texte = Label(
                text="Appuie sur 'Actualiser' pour voir l'historique des alertes.",
                font_size='15sp',
                size_hint_y=None,
                valign='top',
                halign='left'
            )
            self.zone_texte.bind(
                width=lambda instance, value: instance.setter('text_size')(instance, (value, None))
            )
            self.zone_texte.bind(
                texture_size=lambda instance, value: instance.setter('height')(instance, value[1])
            )

            scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
            scroll.add_widget(self.zone_texte)
            layout.add_widget(scroll)

            self.bouton = Button(
                text="Actualiser",
                size_hint=(1, None),
                height=60,
                font_size='18sp'
            )
            self.bouton.bind(on_press=self.actualiser)
            layout.add_widget(self.bouton)

            self.add_widget(layout)

        def actualiser(self, instance):
            self.bouton.disabled = True
            self.zone_texte.text = "Chargement..."
            threading.Thread(target=self._charger_en_arriere_plan).start()

        def _charger_en_arriere_plan(self):
            try:
                alertes = historique_alertes(limite=30)
                texte = self._formater_alertes(alertes)
            except Exception as e:
                texte = f"Erreur : {e}"

            Clock.schedule_once(lambda dt: self._afficher(texte))

        def _afficher(self, texte):
            self.zone_texte.text = texte
            self.bouton.disabled = False

        def _formater_alertes(self, alertes):
            if not alertes:
                return "HISTORIQUE DES ALERTES\n\nAucune alerte enregistrée pour l'instant.\n(Les alertes se déclenchent sur les signaux ACHAT FORT / VENTE FORTE.)"

            lignes = [f"HISTORIQUE DES ALERTES ({len(alertes)})", ""]
            for a in alertes:
                signal = retirer_emojis(a["signal"])
                lignes.append(f"{a['date']} - {a['crypto'].upper()}")
                lignes.append(f"  Signal : {signal}")
                lignes.append(f"  Prix : {a['prix']} $")
                if a.get("score") is not None:
                    lignes.append(f"  Score : {a['score']}/100 | Confiance : {a['confidence']}%")
                lignes.append("")

            return "\n".join(lignes)

    # ========================================================
    # APP PRINCIPALE
    # ========================================================
    class FuturIAApp(App):
        def build(self):
            layout_principal = BoxLayout(orientation='vertical')

            titre = Label(
                text="FuturIA Crypto",
                font_size='22sp',
                size_hint=(1, None),
                height=45,
                bold=True
            )
            layout_principal.add_widget(titre)

            nav = BoxLayout(size_hint=(1, None), height=50, spacing=5, padding=5)
            btn_analyse = Button(text="Analyse", font_size='14sp')
            btn_portefeuille = Button(text="Portefeuille", font_size='14sp')
            btn_alertes = Button(text="Alertes", font_size='14sp')
            nav.add_widget(btn_analyse)
            nav.add_widget(btn_portefeuille)
            nav.add_widget(btn_alertes)
            layout_principal.add_widget(nav)

            self.sm = ScreenManager()
            self.sm.add_widget(EcranAnalyse(name="analyse"))
            self.sm.add_widget(EcranPortefeuille(name="portefeuille"))
            self.sm.add_widget(EcranAlertes(name="alertes"))
            layout_principal.add_widget(self.sm)

            btn_analyse.bind(on_press=lambda x: setattr(self.sm, 'current', 'analyse'))
            btn_portefeuille.bind(on_press=lambda x: setattr(self.sm, 'current', 'portefeuille'))
            btn_alertes.bind(on_press=lambda x: setattr(self.sm, 'current', 'alertes'))

            return layout_principal


    if __name__ == "__main__":
        FuturIAApp().run()

except Exception:
    with open("/storage/emulated/0/FuturIA_Crypto/erreur_app.txt", "w") as f:
        f.write(traceback.format_exc())
