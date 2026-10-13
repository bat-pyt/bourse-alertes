import os
import sys
import json
import cloudscraper
from bs4 import BeautifulSoup

BASE_URL = "https://jeuboursiercreditagricole.abcbourse.com"
GAME_NAME = "alpes-provence"

def creer_session():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

def connecter(scraper, pseudo, password):
    """Tente de se connecter au jeu boursier."""
    login_url = f"{BASE_URL}/api/game/loginUser"
    payload = {
        "pseudo": pseudo,
        "pass": password,
        "stayLog": True,
        "ShortNameGame": GAME_NAME
    }
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Referer": f"{BASE_URL}/game/{GAME_NAME}/ranking",
        "X-Requested-With": "XMLHttpRequest"
    }

    print(f"[*] Connexion en cours pour '{pseudo}'...")
    resp = scraper.post(login_url, json=payload, headers=headers)

    if resp.status_code == 200:
        res_text = resp.text.strip()
        # L'API renvoie "" ou null en cas de succès, sinon un message d'erreur
        if res_text == '""' or res_text == 'null' or res_text == '':
            print("[+] Connexion réussie !")
            return True
        else:
            try:
                err_msg = json.loads(res_text)
                print(f"[-] Échec de connexion : {err_msg}")
            except Exception:
                print(f"[-] Réponse serveur : {res_text}")
            return False
    else:
        print(f"[-] Erreur HTTP {resp.status_code} lors du login.")
        return False

def recuperer_classement(scraper):
    """Télécharge la page du classement et extrait les leaders."""
    url = f"{BASE_URL}/game/{GAME_NAME}/ranking"
    resp = scraper.get(url)
    
    if resp.status_code != 200:
        print(f"[-] Impossible d'accéder au classement (Code {resp.status_code})")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Recherche de la table de classement
    tables = soup.find_all("table")
    print(f"[*] {len(tables)} tables trouvées sur la page de classement.")
    
    lignes_joueurs = []
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all(["td", "th"])
            textes = [c.get_text(strip=True) for c in cols]
            if textes:
                # Vérifie la présence de liens vers les profils/portefeuilles
                liens = [a.get("href") for a in row.find_all("a", href=True)]
                lignes_joueurs.append({"colonnes": textes, "liens": liens})

    return lignes_joueurs

def main():
    print("=" * 60)
    print(f" ESPIONNAGE & COMPARAISON - JEU BOURSIER ({GAME_NAME})")
    print("=" * 60)

    pseudo = input("Entrez votre Pseudo (ex: WarrenBuffett) : ").strip()
    if not pseudo:
        pseudo = "WarrenBuffett"

    import getpass
    password = getpass.getpass("Entrez votre Mot de passe : ").strip()
    if not password:
        print("[-] Mot de passe requis.")
        return

    scraper = creer_session()
    ok = connecter(scraper, pseudo, password)
    
    if not ok:
        print("\n[!] Vérifiez votre mot de passe et réessayez.")
        return

    print("\n[*] Récupération du classement et des portefeuilles...")
    donnees = recuperer_classement(scraper)
    
    print(f"\n[+] Nombre d'entrées extraites : {len(donnees)}")
    for i, d in enumerate(donnees[:15]):
        print(f"  {i+1}. {' | '.join(d['colonnes'])} (Liens: {d['liens']})")

if __name__ == "__main__":
    main()
