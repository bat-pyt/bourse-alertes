import os
import sys
import time
import json
import re
from datetime import datetime
import requests
import yfinance as yf
from bs4 import BeautifulSoup

# Canal Ntfy
NTFY_URL = "https://ntfy.sh/alertebourse"

# Seuil de hausse sur 15 min réelles pour arbitrage
SEUIL_HAUSSE_15MIN = 0.65
# Seuil de stop-loss sur PRU
SEUIL_STOP_LOSS_PRU = -1.5

# Fréquence de scan en secondes
CHECK_INTERVAL_SECONDS = 90
# Durée maximale d'un job GitHub en minutes
MAX_RUN_MINUTES = 450  # Couvre jusqu'à la fermeture des marchés US

# Identifiants lus depuis les Secrets GitHub
JEU_PSEUDO = os.environ.get("JEU_PSEUDO", "WarrenBuffett")
JEU_PASSWORD = os.environ.get("JEU_PASSWORD", "")
BASE_URL = "https://jeuboursiercreditagricole.abcbourse.com"
GAME_NAME = "alpes-provence"

# Positions par défaut en fallback si pas de mot de passe configuré
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


def notifier_mobile(titre: str, message: str, priority: str = "high"):
    try:
        headers = {
            "Title": titre.encode("utf-8"),
            "Priority": priority,
            "Tags": "chart_with_upwards_trend,rocket"
        }
        requests.post(NTFY_URL, data=message.encode("utf-8"), headers=headers, timeout=5)
        print(f"[NOTIF ENVOYÉE] {titre} - {message}")
    except Exception as e:
        print(f"[!] Erreur Ntfy : {e}")


def synchroniser_portefeuille_jeu():
    """Se connecte au jeu boursier et récupère vos vraies positions à jour."""
    if not JEU_PASSWORD:
        print("[i] JEU_PASSWORD non configuré. Utilisation des positions en mémoire.")
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

        print(f"[*] Connexion au jeu boursier pour {JEU_PSEUDO}...")
        resp = scraper.post(login_url, json=payload, headers=headers)
        if resp.status_code != 200:
            return POSITIONS_PAR_DEFAUT

        # Accès à la page du portefeuille
        r_port = scraper.get(f"{BASE_URL}/game/{GAME_NAME}/portfolio")
        if r_port.status_code != 200:
            return POSITIONS_PAR_DEFAUT

        soup = BeautifulSoup(r_port.text, "html.parser")
        positions_trouvees = []

        # Analyse des lignes de tableau contenant des liens 'cotation-'
        for tr in soup.find_all("tr"):
            a_tag = tr.find("a", href=re.compile(r"cotation-"))
            if not a_tag:
                continue
            
            href = a_tag["href"]
            short_id = href.split("cotation-")[-1]
            nom = a_tag.get_text(strip=True)

            # Conversion ticker Yahoo
            ticker_yf = short_id
            if short_id.endswith("p"):
                ticker_yf = short_id[:-1] + ".PA"
            elif short_id.endswith("u"):
                ticker_yf = short_id[:-1]

            # Extraction du PRU (prix de revient)
            cols = [td.get_text(strip=True) for td in tr.find_all("td")]
            pru_val = None
            for c in cols:
                # Cherche un nombre flottant type '15,719' ou '349,93'
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
            print(f"[+] Synchronisation réussie : {len(positions_trouvees)} positions trouvées sur votre compte !")
            return positions_trouvees

    except Exception as e:
        print(f"[!] Erreur synchronisation portefeuille : {e}")

    return POSITIONS_PAR_DEFAUT


def verifier_positions(positions_actuelles):
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
                if gain_pru <= SEUIL_STOP_LOSS_PRU:
                    notifier_mobile(
                        f"🚨 STOP-LOSS : {nom}",
                        f"Cours: {cours_actuel:.2f}€. Perte sur PRU: {gain_pru:.2f}% (Seuil {SEUIL_STOP_LOSS_PRU}%)."
                    )
    except Exception as e:
        print(f"[!] Erreur portefeuille : {e}")


def scanner_arbitrage():
    dict_actions = {a["symbol"]: a["name"] for a in ACTIONS_DISPONIBLES}
    symbols = list(dict_actions.keys())

    try:
        df = yf.download(symbols, period="1d", interval="1m", progress=False)
        if df.empty or "Close" not in df:
            return

        close_df = df["Close"].ffill()
        if len(close_df) < 16:
            return

        prix_actuels = close_df.iloc[-1]
        prix_il_y_a_15m = close_df.iloc[-16]
        variations_15m = ((prix_actuels - prix_il_y_a_15m) / prix_il_y_a_15m) * 100

        for sym, var_15m in variations_15m.items():
            if var_15m is not None and not (var_15m != var_15m):
                if var_15m >= SEUIL_HAUSSE_15MIN:
                    nom = dict_actions.get(sym, sym)
                    p_now = prix_actuels.get(sym, 0.0)
                    p_old = prix_il_y_a_15m.get(sym, 0.0)
                    notifier_mobile(
                        f"🚀 ACHAT JEU : {nom}",
                        f"+{var_15m:.2f}% en 15m ! Cours direct: {p_now:.2f}€ vs jeu ~{p_old:.2f}€"
                    )
    except Exception as e:
        print(f"[!] Erreur scan : {e}")


def main():
    print(f"=== Surveillance GitHub démarrée : {datetime.now()} ===")
    
    # Récupère automatiquement vos vraies positions à jour
    positions_suivies = synchroniser_portefeuille_jeu()
    
    notifier_mobile(
        "🤖 GitHub Bot Démarré", 
        f"Surveillance active de {len(positions_suivies)} positions en direct + scan arbitrage 15 min !"
    )

    t_start = time.time()
    dernier_sync = time.time()

    while (time.time() - t_start) < (MAX_RUN_MINUTES * 60):
        # Resynchronise automatiquement les positions toutes les 30 minutes
        if (time.time() - dernier_sync) > 1800:
            positions_suivies = synchroniser_portefeuille_jeu()
            dernier_sync = time.time()

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle d'analyse ({len(positions_suivies)} positions suivies)...")
        verifier_positions(positions_suivies)
        scanner_arbitrage()
        time.sleep(CHECK_INTERVAL_SECONDS)

    print("=== Fin de la session GitHub (rotation) ===")


if __name__ == "__main__":
    main()
