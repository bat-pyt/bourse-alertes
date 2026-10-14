import os
import sys
import time
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
import requests
import yfinance as yf
from bs4 import BeautifulSoup

# Canal Ntfy
NTFY_URL = "https://ntfy.sh/alertebourse"

# Seuils de surveillance
SEUIL_STOP_LOSS_PRU = -1.5        # Stop-loss strict sur prix d'achat PRU
SEUIL_TRAILING_STOP_REPLI = 1.0   # Si une position a fait > +3%, alerte si repli de plus de 1%
SEUIL_MOMENTUM_JOUR = 2.0         # Alerte si une action du vivier explose de plus de +2% avec cassure

CHECK_INTERVAL_SECONDS = 90
MAX_RUN_MINUTES = 450             # Couvre jusqu'à la fermeture des marchés US

JEU_PSEUDO = os.environ.get("JEU_PSEUDO", "WarrenBuffett")
JEU_PASSWORD = os.environ.get("JEU_PASSWORD", "")
BASE_URL = "https://jeuboursiercreditagricole.abcbourse.com"
GAME_NAME = "alpes-provence"

# Positions par défaut
POSITIONS_PAR_DEFAUT = [
    {"symbol": "GOOG", "name": "Alphabet C", "pru": 349.934},
    {"symbol": "ALO.PA", "name": "Alstom", "pru": 15.719},
    {"symbol": "LVC.PA", "name": "Amundi CAC 40 2X", "pru": 40.669},
    {"symbol": "INR.PA", "name": "Amundi MSCI India", "pru": 24.339},
    {"symbol": "BNP.PA", "name": "BNP Paribas", "pru": 90.308},
    {"symbol": "CAP.PA", "name": "Capgemini", "pru": 115.169},
    {"symbol": "BN.PA", "name": "Danone", "pru": 59.371},
    {"symbol": "SU.PA", "name": "Schneider Electric", "pru": 264.767},
    {"symbol": "SOI.PA", "name": "Soitec", "pru": 156.037},
]

ACTIONS_DISPONIBLES = [
    {"symbol": "TE.PA", "name": "Technip Energies"},
    {"symbol": "TTE.PA", "name": "TotalEnergies"},
    {"symbol": "VK.PA", "name": "Vallourec"},
    {"symbol": "BON.PA", "name": "Bonduelle"},
    {"symbol": "BABA", "name": "Alibaba"},
    {"symbol": "FRVIA.PA", "name": "Forvia"},
    {"symbol": "LVC.PA", "name": "Amundi CAC 40 2X"},
    {"symbol": "INR.PA", "name": "Amundi MSCI India"},
    {"symbol": "NVDA", "name": "Nvidia"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "GOOG", "name": "Alphabet"},
    {"symbol": "AC.PA", "name": "Accor"},
    {"symbol": "AI.PA", "name": "Air Liquide"},
    {"symbol": "AIR.PA", "name": "Airbus"},
    {"symbol": "ALO.PA", "name": "Alstom"},
    {"symbol": "BNP.PA", "name": "BNP Paribas"},
    {"symbol": "BN.PA", "name": "Danone"},
    {"symbol": "CA.PA", "name": "Carrefour"},
    {"symbol": "CAP.PA", "name": "Capgemini"},
    {"symbol": "CS.PA", "name": "AXA"},
    {"symbol": "DG.PA", "name": "Vinci"},
    {"symbol": "DSY.PA", "name": "Dassault Systemes"},
    {"symbol": "EDEN.PA", "name": "Edenred"},
    {"symbol": "EL.PA", "name": "EssilorLuxottica"},
    {"symbol": "EN.PA", "name": "Bouygues"},
    {"symbol": "ENGI.PA", "name": "Engie"},
    {"symbol": "ERF.PA", "name": "Eurofins Scientific"},
    {"symbol": "GLE.PA", "name": "Societe Generale"},
    {"symbol": "HO.PA", "name": "Thales"},
    {"symbol": "KER.PA", "name": "Kering"},
    {"symbol": "LR.PA", "name": "Legrand"},
    {"symbol": "MC.PA", "name": "LVMH"},
    {"symbol": "ML.PA", "name": "Michelin"},
    {"symbol": "MT.AS", "name": "ArcelorMittal"},
    {"symbol": "OR.PA", "name": "L'Oreal"},
    {"symbol": "ORA.PA", "name": "Orange"},
    {"symbol": "PUB.PA", "name": "Publicis Groupe"},
    {"symbol": "RI.PA", "name": "Pernod Ricard"},
    {"symbol": "RMS.PA", "name": "Hermes"},
    {"symbol": "RNO.PA", "name": "Renault"},
    {"symbol": "SAF.PA", "name": "Safran"},
    {"symbol": "SAN.PA", "name": "Sanofi"},
    {"symbol": "SGO.PA", "name": "Saint-Gobain"},
    {"symbol": "STLAP.PA", "name": "Stellantis"},
    {"symbol": "STMPA.PA", "name": "STMicroelectronics"},
    {"symbol": "SU.PA", "name": "Schneider Electric"},
    {"symbol": "TEP.PA", "name": "Teleperformance"},
    {"symbol": "URW.PA", "name": "Unibail-RW"},
    {"symbol": "VIE.PA", "name": "Veolia"},
    {"symbol": "VIV.PA", "name": "Vivendi"},
    {"symbol": "SOI.PA", "name": "Soitec"},
    {"symbol": "WLN.PA", "name": "Worldline"},
    {"symbol": "NEX.PA", "name": "Nexans"},
    {"symbol": "SOP.PA", "name": "Sopra Steria"},
    {"symbol": "ATO.PA", "name": "Atos"},
    {"symbol": "SESG.PA", "name": "SES Imagotag"},
]

# Mémoire des actualités et alertes déjà envoyées pour éviter les doublons
actualites_deja_notifiees = set()
evenements_calendrier_notifies = set()
plus_hauts_positions = {}


def notifier_mobile(titre: str, message: str, priority: str = "high", tags: str = "chart_with_upwards_trend,rocket"):
    try:
        headers = {
            "Title": titre.encode("utf-8"),
            "Priority": priority,
            "Tags": tags
        }
        requests.post(NTFY_URL, data=message.encode("utf-8"), headers=headers, timeout=5)
        print(f"[NOTIF ENVOYÉE] {titre} - {message}")
    except Exception as e:
        print(f"[!] Erreur Ntfy : {e}")


def synchroniser_portefeuille_jeu():
    """Se connecte au jeu boursier et récupère vos vraies positions à jour."""
    if not JEU_PASSWORD:
        return POSITIONS_PAR_DEFAUT

    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        
        login_url = f"{BASE_URL}/api/game/loginUser"
        payload = {
            "pseudo": JEU_PSEUDO,
            "pass": JEU_PASSWORD,
            "stayLog": True,
            "ShortNameGame": GAME_NAME
        }
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": f"{BASE_URL}/game/{GAME_NAME}/ranking",
            "X-Requested-With": "XMLHttpRequest"
        }

        resp = scraper.post(login_url, json=payload, headers=headers)
        if resp.status_code != 200:
            return POSITIONS_PAR_DEFAUT

        r_port = scraper.get(f"{BASE_URL}/game/{GAME_NAME}/portfolio")
        if r_port.status_code != 200:
            return POSITIONS_PAR_DEFAUT

        soup = BeautifulSoup(r_port.text, "html.parser")
        positions_trouvees = []

        for tr in soup.find_all("tr"):
            a_tag = tr.find("a", href=re.compile(r"cotation-"))
            if not a_tag:
                continue
            
            href = a_tag["href"]
            short_id = href.split("cotation-")[-1]
            nom = a_tag.get_text(strip=True)

            ticker_yf = short_id
            if short_id.endswith("p"):
                ticker_yf = short_id[:-1] + ".PA"
            elif short_id.endswith("u"):
                ticker_yf = short_id[:-1]

            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            pru_val = None
            for c in cols:
                match = re.search(r"^\d+([.,]\d+)?$", c)
                if match:
                    try:
                        pru_val = float(c.replace(" ", "").replace(",", "."))
                        break
                    except Exception:
                        pass

            positions_trouvees.append({
                "symbol": ticker_yf,
                "name": nom,
                "pru": pru_val
            })

        if positions_trouvees:
            return positions_trouvees

    except Exception as e:
        print(f"[!] Erreur synchronisation : {e}")

    return POSITIONS_PAR_DEFAUT


def verifier_calendrier_financier(positions_actuelles):
    """
    Vérifie les dates de résultats financiers et détachements de dividendes
    imminents pour vos actions (dans les 7 prochains jours).
    """
    print("[*] Vérification du calendrier financier (Résultats & Dividendes)...")
    aujourdhui = date.today()

    for item in positions_actuelles:
        sym = item["symbol"]
        nom = item["name"]

        try:
            t = yf.Ticker(sym)
            cal = t.calendar
            if not cal:
                continue

            # 1. Vérification des résultats (Earnings)
            earnings = cal.get("Earnings Date")
            if earnings:
                e_date = earnings[0] if isinstance(earnings, list) else earnings
                if isinstance(e_date, datetime):
                    e_date = e_date.date()
                
                if isinstance(e_date, date):
                    jours_restants = (e_date - aujourdhui).days
                    cle = f"{sym}_earnings_{e_date}"
                    if 0 <= jours_restants <= 5 and cle not in evenements_calendrier_notifies:
                        evenements_calendrier_notifies.add(cle)
                        msg_date = "AUJOURD'HUI !" if jours_restants == 0 else f"dans {jours_restants} jour(s) ({e_date.strftime('%d/%m')})"
                        notifier_mobile(
                            f"📅 RÉSULTATS : {nom}",
                            f"Publication des résultats financiers {msg_date}. Forte volatilité attendue !",
                            priority="high",
                            tags="calendar,warning"
                        )

            # 2. Vérification des dividendes (Ex-Dividend Date)
            ex_div = cal.get("Ex-Dividend Date")
            if ex_div:
                if isinstance(ex_div, datetime):
                    ex_div = ex_div.date()
                if isinstance(ex_div, date):
                    jours_div = (ex_div - aujourdhui).days
                    cle = f"{sym}_div_{ex_div}"
                    if 0 <= jours_div <= 5 and cle not in evenements_calendrier_notifies:
                        evenements_calendrier_notifies.add(cle)
                        msg_div = "AUJOURD'HUI" if jours_div == 0 else f"le {ex_div.strftime('%d/%m')}"
                        notifier_mobile(
                            f"💰 DIVIDENDE : {nom}",
                            f"Détachement du dividende prévu {msg_div}. Le cours sera ajusté à l'ouverture.",
                            priority="default",
                            tags="moneybag,bell"
                        )

        except Exception:
            pass


def surveiller_actualites_en_direct(positions_actuelles):
    """
    Scanne les flux d'actualités financières (Google News FR) pour détecter
    les annonces de résultats, contrats, notes d'analystes ou avertissements.
    """
    noms_a_surveiller = [p["name"] for p in positions_actuelles]
    if not noms_a_surveiller:
        return

    # Recherche combinée des mots-clés boursiers importants
    query = "+OR+".join([n.replace(" ", "+") for n in noms_a_surveiller[:6]])
    url = f"https://news.google.com/rss/search?q=({query})+(résultats+OR+bénéfice+OR+chiffre+d'affaires+OR+contrat+OR+dividende+OR+recommandation)+when:1d&hl=fr&gl=FR&ceid=FR:fr"

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return

        root = ET.fromstring(r.content)
        items = root.findall(".//item")

        for it in items[:15]:
            titre = it.find("title").text if it.find("title") is not None else ""
            if not titre or titre in actualites_deja_notifiees:
                continue

            # Vérifie si le titre concerne explicitement une de nos actions
            for nom in noms_a_surveiller:
                # Recherche du nom dans le titre (insensible à la casse)
                if re.search(r"\b" + re.escape(nom) + r"\b", titre, re.IGNORECASE):
                    actualites_deja_notifiees.add(titre)
                    notifier_mobile(
                        f"📰 ACTUALITÉ : {nom}",
                        titre,
                        priority="default",
                        tags="newspaper,mega"
                    )
                    break

    except Exception as e:
        print(f"[!] Erreur scan actualités : {e}")


def verifier_positions(positions_actuelles):
    """
    Surveillance stricte du portefeuille :
    1. Stop-Loss PRU (couper si <= -1.5%).
    2. Trailing Stop (sécuriser les gains si un gros gagnant décroche).
    """
    symbols = [p["symbol"] for p in positions_actuelles]
    try:
        data = yf.download(symbols, period="5d", progress=False)
        if data.empty or "Close" not in data:
            return
        close_df = data["Close"].ffill()

        for item in positions_actuelles:
            sym = item["symbol"]
            nom = item["name"]
            pru = item.get("pru")

            if sym not in close_df or len(close_df[sym].dropna()) < 2:
                continue

            serie = close_df[sym].dropna()
            cours_actuel = serie.iloc[-1]

            if pru:
                gain_pru = ((cours_actuel - pru) / pru) * 100

                # 1. Alerte Stop-Loss strict
                if gain_pru <= SEUIL_STOP_LOSS_PRU:
                    notifier_mobile(
                        f"🚨 STOP-LOSS : {nom}",
                        f"Cours: {cours_actuel:.2f}€. Perte sur PRU: {gain_pru:.2f}% (Seuil {SEUIL_STOP_LOSS_PRU}%). Coupez pour préserver le capital !",
                        priority="urgent",
                        tags="rotating_light,x"
                    )

                # 2. Trailing Stop (sécurisation des plus-values)
                max_connu = plus_hauts_positions.get(sym, gain_pru)
                if gain_pru > max_connu:
                    plus_hauts_positions[sym] = gain_pru
                    max_connu = gain_pru

                # Si la position a fait au moins +3% et qu'elle décroche de plus de 1% depuis son sommet
                if max_connu >= 3.0 and (max_connu - gain_pru) >= SEUIL_TRAILING_STOP_REPLI:
                    notifier_mobile(
                        f"🎯 SÉCURISER GAINS : {nom}",
                        f"Gain actuel: +{gain_pru:.2f}% (était monté à +{max_connu:.2f}%). Repli constaté, pensez à encaisser !",
                        priority="high",
                        tags="money_with_wings,bell"
                    )
                    # Remet à niveau le max pour ne pas spammer
                    plus_hauts_positions[sym] = gain_pru

    except Exception as e:
        print(f"[!] Erreur portefeuille : {e}")


def scanner_momentum_et_breakouts():
    """
    Scanne l'univers d'investissement pour détecter les fusées du jour (Momentum >= +2%).
    """
    dict_actions = {a["symbol"]: a["name"] for a in ACTIONS_DISPONIBLES}
    symbols = list(dict_actions.keys())

    try:
        data = yf.download(symbols, period="5d", progress=False)
        if data.empty or "Close" not in data:
            return

        close_df = data["Close"].ffill()
        for sym, nom in dict_actions.items():
            if sym not in close_df or len(close_df[sym].dropna()) < 2:
                continue

            serie = close_df[sym].dropna()
            cours_actuel = serie.iloc[-1]
            cours_veille = serie.iloc[-2]

            var_jour = ((cours_actuel - cours_veille) / cours_veille) * 100

            if var_jour >= SEUIL_MOMENTUM_JOUR:
                # Alerte momentum fort
                cle_mom = f"mom_{sym}_{date.today()}"
                if cle_mom not in actualites_deja_notifiees:
                    actualites_deja_notifiees.add(cle_mom)
                    notifier_mobile(
                        f"🚀 MOMENTUM FORT : {nom}",
                        f"+{var_jour:.2f}% aujourd'hui (cours: {cours_actuel:.2f}€). Forte impulsion haussière !",
                        priority="high",
                        tags="fire,chart_with_upwards_trend"
                    )

    except Exception as e:
        print(f"[!] Erreur scan momentum : {e}")


def main():
    print(f"=== Surveillance GitHub démarrée : {datetime.now()} ===")
    
    positions_suivies = synchroniser_portefeuille_jeu()
    
    notifier_mobile(
        "🤖 Scanner Bourse & Actualités Actif", 
        f"Surveillance de {len(positions_suivies)} positions en direct (Résultats, Dividendes, News, Stop-Loss et Momentum)",
        priority="default",
        tags="white_check_mark,robot"
    )

    # Vérification initiale du calendrier financier
    verifier_calendrier_financier(positions_suivies)
    surveiller_actualites_en_direct(positions_suivies)

    t_start = time.time()
    dernier_sync = time.time()
    dernier_scan_news = time.time()
    dernier_scan_cal = time.time()

    while (time.time() - t_start) < (MAX_RUN_MINUTES * 60):
        t_actuel = time.time()

        # Resynchronisation du portefeuille toutes les 30 minutes
        if (t_actuel - dernier_sync) > 1800:
            positions_suivies = synchroniser_portefeuille_jeu()
            dernier_sync = t_actuel

        # Scan des actualités financières toutes les 15 minutes
        if (t_actuel - dernier_scan_news) > 900:
            surveiller_actualites_en_direct(positions_suivies)
            dernier_scan_news = t_actuel

        # Vérification du calendrier financier toutes les 2 heures
        if (t_actuel - dernier_scan_cal) > 7200:
            verifier_calendrier_financier(positions_suivies)
            dernier_scan_cal = t_actuel

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle d'analyse ({len(positions_suivies)} positions)...")
        verifier_positions(positions_suivies)
        scanner_momentum_et_breakouts()
        time.sleep(CHECK_INTERVAL_SECONDS)

    print("=== Fin de la session GitHub (rotation) ===")


if __name__ == "__main__":
    main()
