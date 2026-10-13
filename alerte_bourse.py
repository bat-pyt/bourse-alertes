import os
import sys
import time
import subprocess
import requests
from datetime import datetime
import yfinance as yf
from windows_toasts import Toast, WindowsToaster

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerte_bourse.log")

def log_msg(msg: str):
    """Écrit un message dans la console et dans le fichier alerte_bourse.log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = msg
    for code in ["\033[91m", "\033[92m", "\033[93m", "\033[96m", "\033[95m", "\033[1m", "\033[0m"]:
        clean_msg = clean_msg.replace(code, "")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {clean_msg}\n")
    except Exception:
        pass

    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))


# Couleurs pour le terminal
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    RED = Fore.RED + Style.BRIGHT
    YELLOW = Fore.YELLOW
    GREEN = Fore.GREEN + Style.BRIGHT
    CYAN = Fore.CYAN + Style.BRIGHT
    MAGENTA = Fore.MAGENTA + Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    RED = ""
    YELLOW = ""
    GREEN = ""
    CYAN = ""
    MAGENTA = ""
    RESET = ""

# ==============================================================================
# 1. VOS POSITIONS RÉELLES EN PORTEFEUILLE (WarrenBuffett)
# ==============================================================================
MES_POSITIONS = [
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

# Stop-Loss serré sur votre prix d'achat PRU (en %) pour éviter les gros gadins
SEUIL_STOP_LOSS_PRU = -1.5

# Alerte si baisse journalière marquée (en %)
SEUIL_BAISSE_JOUR = -1.2


# ==============================================================================
# 2. UNIVERS ÉLARGI DE SURVEILLANCE ARBITRAGE (CAC40 + SBF120 Volatiles + US + ETFs)
# ==============================================================================
import json

# Fichier catalogue complet généré par extraire_catalogue_jeu.py
CATALOGUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "actions_plateforme.json")

def charger_actions_disponibles():
    """Charge le catalogue complet aspiré du jeu ou utilise le vivier par défaut."""
    if os.path.exists(CATALOGUE_FILE):
        try:
            with open(CATALOGUE_FILE, "r", encoding="utf-8") as f:
                actions = json.load(f)
                if actions and len(actions) > 0:
                    return actions
        except Exception as e:
            print(f"[!] Erreur lecture {CATALOGUE_FILE}: {e}")
    
    # Vivier étendu par défaut
    return [
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

ACTIONS_DISPONIBLES = charger_actions_disponibles()

# NOUVEAU SEUIL OPTIMISÉ POUR L'ARBITRAGE DE LATENCE (en %)
# Déclenche dès +0.65% de hausse en 15 minutes réelles
SEUIL_HAUSSE_15MIN = 0.65

# Vitesse du scan : 90 secondes (1 min 30) pour réagir immédiatement dès la formation du mouvement
CHECK_INTERVAL_SECONDS = 90


# ==============================================================================
# GESTION DES NOTIFICATIONS (WINDOWS TOAST + SMARTPHONE NTFY)
# ==============================================================================
_toaster = WindowsToaster("Alerte Bourse")
NTFY_URL = "https://ntfy.sh/alertebourse"

def envoyer_notification(titre: str, message: str, priority: str = "high"):
    """Affiche une notification toast Windows et l'envoie sur votre téléphone via ntfy."""
    # 1. Notification bureau Windows
    try:
        t = Toast()
        t.text_fields = [titre, message]
        _toaster.show_toast(t)
    except Exception as e:
        pass

    # 2. Notification Smartphone (ntfy.sh)
    try:
        headers = {
            "Title": titre.encode("utf-8"),
            "Priority": priority,
            "Tags": "chart_with_upwards_trend,bell"
        }
        requests.post(NTFY_URL, data=message.encode("utf-8"), headers=headers, timeout=5)
    except Exception as e:
        print(f"[!] Erreur notification ntfy : {e}")


def verifier_mes_positions():
    """Surveille votre portefeuille : Stop-Loss PRU et baisse journalière."""
    if not MES_POSITIONS:
        return

    log_msg(f"\n{CYAN}--- 1. ANALYSE PORTEFEUILLE (Stop PRU <= {SEUIL_STOP_LOSS_PRU}% | Jour <= {SEUIL_BAISSE_JOUR}%) ---{RESET}")
    symbols = [p["symbol"] for p in MES_POSITIONS]

    try:
        data = yf.download(symbols, period="5d", progress=False)
        if data.empty or "Close" not in data:
            log_msg("[i] Données du portefeuille indisponibles.")
            return

        close_df = data["Close"].ffill()
        for item in MES_POSITIONS:
            sym = item["symbol"]
            nom = item["name"]
            pru = item.get("pru")

            try:
                # Si multi-tickers, close_df est un DataFrame
                if sym not in close_df or len(close_df[sym].dropna()) < 2:
                    continue

                serie = close_df[sym].dropna()
                cours_actuel = serie.iloc[-1]
                cours_veille = serie.iloc[-2]

                var_jour = ((cours_actuel - cours_veille) / cours_veille) * 100
                signe_j = "+" if var_jour >= 0 else ""

                info_pru = ""
                alerte_pru = False
                if pru:
                    gain_pru = ((cours_actuel - pru) / pru) * 100
                    signe_p = "+" if gain_pru >= 0 else ""
                    info_pru = f" | PRU: {pru:.2f} ({signe_p}{gain_pru:.2f}%)"
                    if gain_pru <= SEUIL_STOP_LOSS_PRU:
                        alerte_pru = True

                if alerte_pru:
                    msg = f"{RED}🚨 [STOP-LOSS PRU ATTEINT] {nom} ({sym}) : {cours_actuel:.2f} €{info_pru} | Jour: {signe_j}{var_jour:.2f}%{RESET}"
                    log_msg(msg)
                    envoyer_notification(
                        f"🚨 STOP-LOSS : {nom}",
                        f"Cours: {cours_actuel:.2f}€. Perte sur PRU: {gain_pru:.2f}% (Seuil {SEUIL_STOP_LOSS_PRU}%). Coupez pour préserver le cash !"
                    )
                elif var_jour <= SEUIL_BAISSE_JOUR:
                    msg = f"{RED}⚠️ [ALERTE BAISSE JOUR] {nom} ({sym}) : {cours_actuel:.2f} €{info_pru} | Jour: {signe_j}{var_jour:.2f}%{RESET}"
                    log_msg(msg)
                    envoyer_notification(
                        f"⚠️ Alerte Baisse : {nom}",
                        f"Chute journalière de {signe_j}{var_jour:.2f}%. Cours actuel: {cours_actuel:.2f}€"
                    )
                elif var_jour < 0:
                    log_msg(f"{YELLOW}[Léger repli] {nom} ({sym}) : {cours_actuel:.2f} €{info_pru} | Jour: {signe_j}{var_jour:.2f}%{RESET}")
                else:
                    log_msg(f"{GREEN}[En hausse] {nom} ({sym}) : {cours_actuel:.2f} €{info_pru} | Jour: {signe_j}{var_jour:.2f}%{RESET}")

            except Exception as err:
                log_msg(f"[!] Erreur sur {sym} : {err}")

    except Exception as e:
        log_msg(f"[!] Erreur globale portefeuille : {e}")


def scanner_opportunites_arbitrage_15min():
    """
    Scanne l'ensemble du vivier pour détecter les hausses >= +0.65% sur 15 min.
    Permet d'acheter au cours différé du jeu avant la répercussion du mouvement.
    """
    log_msg(f"\n{MAGENTA}--- 2. SCAN ARBITRAGE DIFFÉRÉ 15 MIN (Signal d'achat si >= +{SEUIL_HAUSSE_15MIN}%) ---{RESET}")
    dict_actions = {a["symbol"]: a["name"] for a in ACTIONS_DISPONIBLES}
    symbols = list(dict_actions.keys())

    try:
        # Télécharge les données 1 minute pour toutes les actions d'un coup
        df = yf.download(symbols, period="1d", interval="1m", progress=False)
        if df.empty or "Close" not in df:
            log_msg("[i] Marché fermé ou données 1m non disponibles.")
            return

        close_df = df["Close"].ffill()
        if len(close_df) < 16:
            log_msg(f"[i] Moins de 15 minutes de cotation aujourd'hui ({len(close_df)} barres).")
            return

        # Comparaison temps réel vs il y a 15 minutes
        prix_actuels = close_df.iloc[-1]
        prix_il_y_a_15m = close_df.iloc[-16]
        variations_15m = ((prix_actuels - prix_il_y_a_15m) / prix_il_y_a_15m) * 100

        opportunites = []
        for sym, var_15m in variations_15m.items():
            if var_15m is not None and not (var_15m != var_15m):  # ignore NaN
                if var_15m >= SEUIL_HAUSSE_15MIN:
                    nom = dict_actions.get(sym, sym)
                    p_now = prix_actuels.get(sym, 0.0)
                    p_old = prix_il_y_a_15m.get(sym, 0.0)
                    opportunites.append({
                        "symbol": sym,
                        "name": nom,
                        "var_15m": var_15m,
                        "price_now": p_now,
                        "price_15m": p_old
                    })

        if opportunites:
            opportunites.sort(key=lambda x: x["var_15m"], reverse=True)
            log_msg(f"{GREEN}🎯 {len(opportunites)} opportunité(s) d'arbitrage immédiate(s) trouvée(s) :{RESET}")
            for opp in opportunites:
                msg_opp = (
                    f"{GREEN}🚀 ACHAT SUR LE JEU : {opp['name']} ({opp['symbol']}) | "
                    f"+{opp['var_15m']:.2f}% en 15m | Réel: {opp['price_now']:.2f} vs Jeu: ~{opp['price_15m']:.2f}{RESET}"
                )
                log_msg(msg_opp)
                envoyer_notification(
                    f"🚀 ACHAT IMMÉDIAT : {opp['name']}",
                    f"+{opp['var_15m']:.2f}% en 15m ! Cours réel: {opp['price_now']:.2f}€ vs prix différé jeu: ~{opp['price_15m']:.2f}€"
                )
        else:
            log_msg(f"[i] Aucune action n'a accéléré de plus de {SEUIL_HAUSSE_15MIN}% sur les 15 dernières minutes.")

    except Exception as e:
        log_msg(f"[!] Erreur scan arbitrage : {e}")


def main():
    log_msg("=" * 75)
    log_msg(" 🏎️ MOTEUR DE GAINS V2 BOOSTÉ - 'WarrenBuffett'")
    log_msg(f" Portefeuille réel    : {len(MES_POSITIONS)} positions avec Stop-Loss PRU ({SEUIL_STOP_LOSS_PRU}%)")
    log_msg(f" Vivier de scalping   : {len(ACTIONS_DISPONIBLES)} valeurs (Seuil d'achat >= +{SEUIL_HAUSSE_15MIN}% sur 15m)")
    log_msg(f" Fréquence de scan    : Toutes les {CHECK_INTERVAL_SECONDS} secondes (1m30)")
    log_msg("=" * 75)

    try:
        while True:
            horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_msg(f"\n>>> CYCLE D'ANALYSE : {horodatage} <<<")
            verifier_mes_positions()
            scanner_opportunites_arbitrage_15min()
            log_msg(f"Prochain scan dans {CHECK_INTERVAL_SECONDS}s...")
            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log_msg("Arrêt de la surveillance.")
        sys.exit(0)


if __name__ == "__main__":
    main()
