import cloudscraper
import json
from bs4 import BeautifulSoup

def trova_chiave_artworks(dati):
    # Funzione ricorsiva che "scava" nel JSON per trovare l'array 'artworks' ovunque si trovi
    if isinstance(dati, dict):
        if 'artworks' in dati and isinstance(dati['artworks'], list):
            return dati['artworks']
        for v in dati.values():
            risultato = trova_chiave_artworks(v)
            if risultato is not None:
                return risultato
    elif isinstance(dati, list):
        for item in dati:
            risultato = trova_chiave_artworks(item)
            if risultato is not None:
                return risultato
    return None

def ottieni_opere_saatchi(profile_url):
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    print(f"Scaricando i dati da: {profile_url}...\n")
    response = scraper.get(profile_url)
    
    if response.status_code != 200:
        print(f"Errore di connessione: {response.status_code}")
        return None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    script_tag = soup.find('script', id='__NEXT_DATA__') 
    
    if script_tag:
        dati_json = json.loads(script_tag.string)
        
        # Usiamo la nostra funzione "segugio" per trovare le opere
        opere = trova_chiave_artworks(dati_json)
        
        if opere is not None:
            opere_estratte = []
            
            for opera in opere:
                dettagli = {
                    'id': opera.get('artworkID'),
                    'titolo': opera.get('title'),
                    'prezzo_listino': opera.get('listPrice'),
                    'stato': opera.get('originalStatus'),
                    'url_immagine': opera.get('artworkImage'),
                    'link_opera': f"https://www.saatchiart.com{opera.get('pdpUrl')}" if opera.get('pdpUrl') else None
                }
                opere_estratte.append(dettagli)
                
            return opere_estratte
        else:
            print("Errore: la chiave 'artworks' non esiste nel JSON scaricato.")
            return None
    return None

# Esecuzione con il link specifico del portfolio
url_profilo = 'https://www.saatchiart.com/en-lt/account/artworks/2254831' 
opere = ottieni_opere_saatchi(url_profilo)

if opere:
    with open('opere.json', 'w', encoding='utf-8') as f:
        json.dump(opere, f, ensure_ascii=False, indent=2)
    print(f"File opere.json aggiornato con successo! Trovate {len(opere)} opere.")
else:
    print("Nessun dato estratto, il file non è stato modificato.")