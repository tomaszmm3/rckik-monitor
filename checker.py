
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

# ===== Helpery logowania =====
def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)

def getenv_required(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        log(f"❌ Brak wymaganej zmiennej środowiskowej: {name}")
        sys.exit(1)
    return val

def normalize(text: Optional[str]) -> str:
    return " ".join((text or "").split()).lower()

# ===== Logika pobierania z WordPress REST API =====
def query_wp_api(base_url: str, search_text: str, per_page: int = 50) -> List[Dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (RCKiK Monitor; GitHub Actions)",
        "Accept": "application/json",
    }
    params = {
        "search": search_text,
        "per_page": per_page,  # WordPress limit zwykle <= 100
        "_embed": "1",
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

def find_match(items: List[Dict[str, Any]], target_text: str) -> Optional[Dict[str, Any]]:
    """
    Szuka dopasowania po tytule (case-insensitive).
    Zwraca obiekt posta (title/link/date/slug) lub None.
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

# ===== Utrzymanie poprzedniego stanu =====
def load_previous_status(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"found": None, "post": None, "checked_at": None}  # None => brak historii
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"⚠️ Nie można odczytać poprzedniego statusu ({e}). Traktuję jako brak historii.")
        return {"found": None, "post": None, "checked_at": None}

def save_current_status(path: Path, found: bool, post: Optional[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "found": bool(found),
        "post": post or None,
        "checked_at": ts(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"💾 Zapisano aktualny status do: {path}")

def main() -> None:
    # ===== Secrets/ENV =====
    target_url = getenv_required("TARGET_URL")       # np. https://rckik.krakow.pl/api/wp-json/wp/v2/posts
    text_to_check = getenv_required("TEXT_TO_CHECK") # np. Komunikat dot. pobierania krwi w grupie AB +
    status_path = Path(os.environ.get("PREV_STATUS_PATH", ".status/rckik.json"))
    changed_flag = Path(".changed")  # plik-flaga, jeśli stan się zmienił

    log("🚀 Start monitoringu (tylko e-mail przy zmianie stanu).")
    log(f"🔧 TARGET_URL      = {target_url}")
    log(f"🔧 TEXT_TO_CHECK   = {text_to_check}")
    log(f"🔧 PREV_STATUS_PATH= {status_path}")

    try:
        items = query_wp_api(target_url, text_to_check, per_page=50)
        post = find_match(items, text_to_check)
        current_found = post is not None

        prev = load_previous_status(status_path)
        prev_found = prev.get("found")

        log(f"📊 Poprzedni stan: {prev_found} | Bieżący stan: {current_found}")

        # Czy zaszła zmiana stanu? (True->False lub False->True; None traktuj jako "pierwszy zapis")
        state_changed = (prev_found is not None) and (prev_found != current_found)

        # Zapisz nowy status zawsze
        save_current_status(status_path, current_found, post)

        if state_changed:
            log("🔔 ZMIANA STANU WYKRYTA! (utworzę plik .changed, wyślę e-mail i zacommituję status)")
            changed_flag.write_text("1", encoding="utf-8")
            # Zwróć specjalny kod (10), żeby dało się odróżnić w logach — ale nie wymuszaj porażki workflow.
            # W samym workflow użyjemy warunku `if: hashFiles('.changed') != ''`.
            sys.exit(10)
        else:
            log("✅ Brak zmiany stanu. (Nie wysyłam e-maila)")
            # Usuń flagę jeśli istniała (np. po ręcznym rerunie)
            if changed_flag.exists():
                try:
                    changed_flag.unlink()
                except Exception:
                    pass
            sys.exit(0)

    except requests.HTTPError as e:
        log(f"❌ Błąd HTTP: {e}")
        if hasattr(e, "response") and e.response is not None:
            log(f"HTTP status: {e.response.status_code}")
            log(f"Treść: {e.response.text[:500]}")
        # Przy błędzie sieci nie chcemy spamować mailami ==> exit(1) i bez .changed
        sys.exit(1)
    except requests.RequestException as e:
        log(f"❌ Błąd sieci: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Nieoczekiwany błąd: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
