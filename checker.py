
import os
import sys
import json
import time
import requests
from typing import Optional, Dict, Any, List

def ts() -> str:
    """Znacznik czasu w logach."""
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str) -> None:
    """Prosty logger na stdout."""
    print(f"[{ts()}] {msg}", flush=True)

def getenv_required(name: str) -> str:
    """Pobiera wymagane zmienne środowiskowe; jeśli brak – loguje i kończy z błędem."""
    val = os.environ.get(name)
    if not val:
        log(f"❌ Brak wymaganej zmiennej środowiskowej: {name}")
        sys.exit(1)
    return val

def normalize(text: Optional[str]) -> str:
    """Normalizacja białych znaków + lower-case."""
    return " ".join((text or "").split()).lower()

def query_wp_api(base_url: str, search_text: str, per_page: int = 50) -> List[Dict[str, Any]]:
    """
    Odpytuje WordPress REST API o posty z dopasowaniem 'search'.
    Zwraca listę obiektów wpisów.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (RCKiK Monitor; GitHub Actions)",
        "Accept": "application/json",
    }
    params = {
        "search": search_text,  # filtr po treści/tytule
        "per_page": per_page,   # WP pozwala zwykle do 100
        "_embed": "1",          # nie wymagane, ale przydatne, zostawiamy
    }

    log(f"ℹ️ Zapytanie do API: {base_url} (search='{search_text}', per_page={per_page})")
    resp = requests.get(base_url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()

    try:
        data = resp.json()
    except json.JSONDecodeError:
        log("❌ Nie udało się zdekodować JSON z odpowiedzi API.")
        sys.exit(1)

    if not isinstance(data, list):
        log("❗ API zwróciło nieoczekiwaną strukturę (nie lista).")
        log(f"Debug payload (skrócone): {str(data)[:500]}")
        sys.exit(1)

    log(f"✅ Otrzymano {len(data)} rekordów z API.")
    return data

def find_announcement(items: List[Dict[str, Any]], target_text: str) -> Optional[Dict[str, Any]]:
    """
    Przeszukuje listę postów pod kątem dopasowania w tytule (case-insensitive).
    Zwraca obiekt posta lub None.
    """
    target_norm = normalize(target_text)

    for idx, item in enumerate(items, start=1):
        title = (item.get("title") or {}).get("rendered") or ""
        link = item.get("link") or ""
        date = item.get("date") or ""
        slug = item.get("slug") or ""
        title_norm = normalize(title)

        log(f"🔎 [{idx}] Tytuł='{title}' | Data='{date}' | Slug='{slug}'")
        if target_norm in title_norm:
            log("🎯 Dopasowanie znalezione w tytule.")
            return {"title": title, "link": link, "date": date, "slug": slug}

    return None

def main() -> None:
    # 1) Pobierz zmienne środowiskowe z secrets
    target_url = getenv_required("TARGET_URL")   # np. https://rckik.krakow.pl/api/wp-json/wp/v2/posts
    text_to_check = getenv_required("TEXT_TO_CHECK")  # np. Komunikat dot. pobierania krwi w grupie AB +

    log("🚀 Start monitoringu RCKiK (GitHub Actions).")
    log(f"🔧 TARGET_URL   = {target_url}")
    log(f"🔧 TEXT_TO_CHECK= {text_to_check}")

    try:
        # 2) Zapytanie do API WP
        items = query_wp_api(target_url, text_to_check, per_page=50)

        # 3) Dopasowanie
        post = find_announcement(items, text_to_check)
        if post:
            log("✅ Ogłoszenie znalezione.")
            log(f"• Tytuł : {post['title']}")
            log(f"• Data  : {post['date']}")
            log(f"• Link  : {post['link']}")
            log(f"• Slug  : {post['slug']}")
            sys.exit(0)  # sukces
        else:
            log("❌ Ogłoszenie NIE zostało znalezione w zwróconych wpisach.")
            sys.exit(1)

    except requests.HTTPError as e:
        log(f"❌ Błąd HTTP podczas zapytania: {e}")
        # Opcjonalnie: log treści błędu jeśli dostępny
        if hasattr(e, 'response') and e.response is not None:
            log(f"HTTP status: {e.response.status_code}")
            log(f"Treść: {e.response.text[:500]}")
        sys.exit(1)
    except requests.RequestException as e:
        log(f"❌ Błąd sieci: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Nieoczekiwany błąd: {e}")
        sys.exit(1)

if __name__ == "__main__":
