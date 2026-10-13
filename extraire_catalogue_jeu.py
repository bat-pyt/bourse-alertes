import os
import sys
import json
import string
import cloudscraper
from bs4 import BeautifulSoup

BASE_URL = "https://jeuboursiercreditagricole.abcbourse.com"
GAME_NAME = "alpes-provence"
OUTPUT_FILE = "actions_plateforme.json"

def extraire_toutes_les_actions(scraper):
    """
    Explore la page des cotations et utilise l'autocomplétion connectée 
    pour extraire 100% des instruments négociables (actions FR, US, ETFs).
    """
    print("[*] Analyse de la page des cotations...")
    resp = scraper.get(f"{BASE_URL}/game/{GAME_NAME}/cotations")
    soup = BeautifulSoup(resp.text, "html.parser")

    # Récupération de la clé hidTradable présente une fois connecté
    hid_el = soup.find(id="hidTradable")
    tradable_val = hid_el.get("value", "") if hid_el else ""
    print(f"[*] Clé de négociation 'hidTradable' : '{tradable_val}'")

    actions_trouvees = {}

    # 1. Liens directs dans la page cotations
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "cotation-" in href:
            code = href.split("cotation-")[-1].strip()
            nom = a.get_text(strip=True)
            if code and nom:
                actions_trouvees[code] = {"name": nom, "short_id": code}

    print(f"[+] {len(actions_trouvees)} actions trouvées directement sur la page.")

    # 2. Requêtes systématiques via l'API d'autocomplétion (lettres a-z, chiffres 0-9)
    print("[*] Scan exhaustif de l'API d'autocomplétion de la plateforme...")
    lettres = list(string.ascii_lowercase) + [str(i) for i in range(10)]
    
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": f"{BASE_URL}/game/{GAME_NAME}/cotations",
        "X-Requested-With": "XMLHttpRequest"
    }

    for lettre in lettres:
        payload = {
            "q": lettre,
            "limit": 100,
            "tradableM": tradable_val
        }
        try:
            r = scraper.post(f"{BASE_URL}/api/game/autocomplete", json=payload, headers=headers)
            if r.status_code == 200:
                items = r.json()
                if items:
                    for item in items:
                        # Ex: item = {'Name': 'TOTALENERGIES', 'ShortID': 'TTEp', 'Place': 160, ...}
                        sid = item.get("ShortID")
                        nom = item.get("Name")
                        if sid and nom:
                            actions_trouvees[sid] = {
                                "name": nom,
                                "short_id": sid,
                                "place": item.get("Place", 160)
                            }
        except Exception:
            pass

    print(f"[+] Total final d'actions uniques négociables sur le jeu : {len(actions_trouvees)}")
    
    # Conversion vers les tickers Yahoo Finance
    # Les codes abcbourse : '...p' = Euronext Paris (.PA), '...u' = US (action directe ou NASDAQ/NYSE)
    liste_yahoo = []
    for sid, data in actions_trouvees.items():
        nom = data["name"]
        ticker_yf = sid
        if sid.endswith("p"):
            # Ex: TTEp -> TTE.PA, ALOp -> ALO.PA
            ticker_yf = sid[:-1] + ".PA"
        elif sid.endswith("u"):
            # Ex: GOOGu -> GOOG, AAPLu -> AAPL, BABAu -> BABA
            ticker_yf = sid[:-1]
        
        liste_yahoo.append({
            "symbol": ticker_yf,
            "name": nom,
            "short_id": sid
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(liste_yahoo, f, ensure_ascii=False, indent=2)

    print(f"[+] Liste complète enregistrée dans '{OUTPUT_FILE}' !")
    return liste_yahoo

def main():
    from espion_classement import creer_session, connecter
    import getpass

    print("=" * 65)
    print(" EXTRACTION DE TOUTES LES ACTIONS NÉGOCIABLES DU JEU BOURSIER")
    print("=" * 65)

    pseudo = input("Pseudo [WarrenBuffett] : ").strip() or "WarrenBuffett"
    pwd = getpass.getpass("Mot de passe : ").strip()

    scraper = creer_session()
    if not connecter(scraper, pseudo, pwd):
        print("[-] Connexion échouée.")
        return

    actions = extraire_toutes_les_actions(scraper)
    print(f"\nExemples d'actions récupérées ({len(actions)} au total) :")
    for a in actions[:10]:
        print(f"  • {a['name']} -> Yahoo: {a['symbol']} (Jeu: {a['short_id']})")

if __name__ == "__main__":
    main()
