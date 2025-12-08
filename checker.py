
import requests

URL = "https://rckik.krakow.pl/api/wp-json/wp/v2/posts?_embed"
TARGET = "Komunikat dot. pobierania krwi w grupie AB +"

def has_announcement(url: str, target_text: str) -> bool:
    # Ustaw nagłówki + timeout, żeby uniknąć blokad i wiszących połączeń
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    

    # Normalizacja białych znaków i porównanie bez uwzględniania wielkości liter
    html = " ".join(resp.text.split())
    return target_text.lower() in html.lower()

if __name__ == "__main__":
    try:
        found = has_announcement(URL, TARGET)
        if found:
            sys.exit(0)
        else:
            sys.exit(1)
    except requests.RequestException as e:
        sys.exit(1)
