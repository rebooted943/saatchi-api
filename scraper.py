import cloudscraper
import json
from bs4 import BeautifulSoup

def ottieni_opere_saatchi(profile_url):
    # Usiamo cloudscraper al posto di requests
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
        try:
            opere = dati_json['props']['pageProps']['initialState']['page']['data']['artworks']
            opere_estratte = []
            
            for opera in opere:
                dettagli = {
                    'id': opera.get('artworkID'),
                    'titolo': opera.get('title'),
                    'prezzo_listino': opera.get('listPrice'),
                    'stato': opera.get('originalStatus'),
                    'url_immagine': opera.get('artworkImage'),
                    'link_opera': f"https://www.saatchiart.com{opera.get('pdpUrl')}"
                }
                opere_estratte.append(dettagli)
                
            return opere_estratte
            
        except KeyError as e:
            print(f"Errore chiave: {e}")
            return None
    return None

# Esecuzione
url_profilo = 'https://www.saatchiart.com/andreeagabrielatudor' 
opere = ottieni_opere_saatchi(url_profilo)

if opere:
    with open('opere.json', 'w', encoding='utf-8') as f:
        json.dump(opere, f, ensure_ascii=False, indent=2)
    print("File opere.json aggiornato con successo!")
else:
    print("Nessun dato estratto, il file non è stato modificato.")