import json
import os
import re
from pathlib import Path

from bs4 import BeautifulSoup

IMAGES_DIR = Path("images")
PROFILE_URL = "https://www.saatchiart.com/andreeagabrielatudor"
# Dashboard URL kept as fallback: it is public but locale-specific.
FALLBACK_URLS = [
    "https://www.saatchiart.com/account/artworks/2254831",
    "https://www.saatchiart.com/en-lt/account/artworks/2254831",
]

REPO = os.environ.get("GITHUB_REPOSITORY", "rebooted943/saatchi-api")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")


def trova_chiave_artworks(dati):
    """Scava nel JSON Next.js e restituisce il primo array 'artworks' di oggetti."""
    if isinstance(dati, dict):
        artworks = dati.get("artworks")
        if isinstance(artworks, list) and artworks and isinstance(artworks[0], dict):
            return artworks
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


def fetch_html(url):
    """
    Saatchi Art (Akamai) blocca i client HTTP senza fingerprint TLS da browser.
    curl_cffi impersona Chrome; cloudscraper resta solo come fallback.
    """
    errors = []

    try:
        from curl_cffi import requests as cf_requests

        response = cf_requests.get(url, impersonate="chrome", timeout=40)
        if response.status_code == 200 and "__NEXT_DATA__" in response.text:
            return response
        errors.append(f"curl_cffi status={response.status_code}")
    except Exception as exc:
        errors.append(f"curl_cffi: {exc}")

    try:
        import cloudscraper

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        response = scraper.get(url, timeout=40)
        if response.status_code == 200 and "__NEXT_DATA__" in response.text:
            return response
        errors.append(f"cloudscraper status={getattr(response, 'status_code', '?')}")
    except Exception as exc:
        errors.append(f"cloudscraper: {exc}")

    print(f"Errore di connessione per {url}: {'; '.join(errors)}")
    return None


def http_get_bytes(url):
    """Scarica un file senza Referer: il CDN Saatchi risponde 403 se vede un sito terzo."""
    try:
        from curl_cffi import requests as cf_requests

        response = cf_requests.get(url, impersonate="chrome", timeout=40)
        if response.status_code == 200 and response.content:
            return response.content, response.headers.get("content-type", "")
    except Exception:
        pass

    try:
        import cloudscraper

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        response = scraper.get(url, timeout=40)
        if response.status_code == 200 and response.content:
            return response.content, response.headers.get("content-type", "")
    except Exception:
        pass

    return None, ""


def url_immagine_pubblica(artwork_id):
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/images/{artwork_id}.jpg"


def varianti_immagine(url):
    """
    Saatchi usa un suffisso numerico per la dimensione:
    -6 thumbnail, -7 media, -8 piena qualità.
    Proviamo dalla più grande alla più piccola, poi l'URL originale.
    """
    if not url:
        return []

    seen = []
    sized = re.sub(r"-(\d+)\.(jpg|jpeg|png|webp)$", r"-{size}.\2", url, flags=re.I)
    if "{size}" in sized:
        for size in (8, 7, 6, 4):
            candidate = sized.replace("{size}", str(size))
            if candidate not in seen:
                seen.append(candidate)
    if url not in seen:
        seen.append(url)
    return seen


def scarica_immagine(artwork_id, source_url):
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMAGES_DIR / f"{artwork_id}.jpg"

    for candidate in varianti_immagine(source_url):
        body, content_type = http_get_bytes(candidate)
        if not body:
            continue
        if "html" in (content_type or "").lower():
            continue
        if len(body) < 1024:
            continue
        dest.write_bytes(body)
        print(f"  Immagine salvata: {dest.name} ({len(body)} byte) da {candidate}")
        return dest, candidate

    print(f"  Impossibile scaricare l'immagine per {artwork_id} ({source_url})")
    return None, source_url


def estrai_immagine(opera):
    for key in ("artworkImage", "imageUrl", "image", "thumbnail", "thumbUrl"):
        value = opera.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
        if isinstance(value, dict):
            for nested in ("url", "src", "artworkImage", "large", "original"):
                nested_val = value.get(nested)
                if isinstance(nested_val, str) and nested_val.startswith("http"):
                    return nested_val
    return None


def ottieni_opere_saatchi(profile_url):
    print(f"Scaricando i dati da: {profile_url}...\n")
    response = fetch_html(profile_url)
    if response is None:
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag or not script_tag.string:
        print("Errore: __NEXT_DATA__ non trovato nella pagina.")
        return None

    dati_json = json.loads(script_tag.string)
    opere = trova_chiave_artworks(dati_json)
    if opere is None:
        print("Errore: la chiave 'artworks' non esiste nel JSON scaricato.")
        return None

    opere_estratte = []
    ids_ok = set()

    for opera in opere:
        artwork_id = str(opera.get("artworkID") or opera.get("id") or "")
        source_image = estrai_immagine(opera)
        local_path, used_url = (None, source_image)
        if artwork_id and source_image:
            local_path, used_url = scarica_immagine(artwork_id, source_image)

        pdp = opera.get("pdpUrl")
        dettagli = {
            "id": artwork_id or None,
            "titolo": opera.get("title"),
            "prezzo_listino": opera.get("listPrice"),
            "stato": opera.get("originalStatus"),
            # URL rehostate: il CDN Saatchi blocca l'hotlink (403) se il browser
            # invia un Referer di un altro sito, quindi le img nel frontend non partono.
            "url_immagine": url_immagine_pubblica(artwork_id) if local_path else used_url,
            "url_immagine_saatchi": used_url or source_image,
            "link_opera": f"https://www.saatchiart.com{pdp}" if pdp else None,
        }
        if local_path:
            ids_ok.add(artwork_id)
        opere_estratte.append(dettagli)

    if ids_ok and IMAGES_DIR.exists():
        for stale in IMAGES_DIR.glob("*.jpg"):
            if stale.stem not in ids_ok:
                stale.unlink()
                print(f"  Rimossa immagine obsoleta: {stale.name}")

    return opere_estratte


if __name__ == "__main__":
    opere = ottieni_opere_saatchi(PROFILE_URL)
    if not opere:
        for fallback in FALLBACK_URLS:
            opere = ottieni_opere_saatchi(fallback)
            if opere:
                break

    if opere:
        with open("opere.json", "w", encoding="utf-8") as f:
            json.dump(opere, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"File opere.json aggiornato con successo! Trovate {len(opere)} opere.")
        missing = [o["id"] for o in opere if not (IMAGES_DIR / f"{o['id']}.jpg").exists()]
        if missing:
            raise SystemExit(f"Attenzione: immagini mancanti per gli id {missing}")
    else:
        raise SystemExit("Nessun dato estratto, il file non è stato modificato.")
