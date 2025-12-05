
import os, sys, time, re
import requests
from bs4 import BeautifulSoup

# --- Konfiguracja z sekretów ---
PRIMARY_URL = os.getenv("TARGET_URL")  # np. https://rckik.krakow.pl/aktualnosci
TEXT_TO_CHECK = os.getenv("TEXT_TO_CHECK")  # np. Komunikat dot. pobierania krwi w grupie AB +

# --- Dodatkowe adresy do sprawdzenia (fallbacki) ---
FALLBACK_URLS = [
    "https://rckik.krakow.pl/",  # strona główna (sekcja "Aktualności")
    "https://rckik.krakow.pl/aktualnosci/komunikat-dot-pobierania-krwi-w-grupie-ab",  # podstrona wpisu
]

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def fetch_with_retries(url, retries=2, timeout=30, backoff=3):
    last_exc = None
    for _ in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if not resp.encoding:
                resp.encoding = "utf-8"
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
    raise last_exc

def normalize_spaces(text: str) -> str:
    # Zamiana niełamliwych spacji na zwykłe + redukcja wielokrotnych odstępów
    text = (text or "").replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def build_variants(base: str):
    """Warianty frazy: małe litery, różne odstępy przy '+' w 'AB +'."""
    b = normalize_spaces(base).lower()
    variants = set()
    variants.add(b)
    # Warianty dla 'ab +' ↔ 'ab+'
    variants.add(b.replace(" ab +", " ab+"))
    variants.add(b.replace(" ab+", " ab +"))
    # Ostrożnie: jeśli ktoś poda frazę bez '+', nie tworzymy dziwnych wariantów
    return variants

def page_contains_text(url: str, variants: set) -> bool:
    resp = fetch_with_retries(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)
    page_norm = normalize_spaces(page_text).lower()
    return any(v in page_norm for v in variants)

def main():
    if not PRIMARY_URL or not TEXT_TO_CHECK:
        print("[ERROR] Brak TARGET_URL lub TEXT_TO_CHECK w env.")
        sys.exit(2)

    print(f"[INFO] Główny adres: {PRIMARY_URL}")
    print(f"[INFO] Długość frazy do sprawdzenia: {len(TEXT_TO_CHECK)}")

    variants = build_variants(TEXT_TO_CHECK)
    print(f"[DEBUG] Liczba wariantów wzorca: {len(variants)}")

    urls_to_check = [PRIMARY_URL] + FALLBACK_URLS
    any_found = False
    errors = []

    for u in urls_to_check:
        try:
            found = page_contains_text(u, variants)
            print(f"[DEBUG] URL: {u} -> {'FOUND' if found else 'NOT_FOUND'}")
            if found:
                any_found = True
                break
        except Exception as e:
            errors.append(f"{u}: {e}")

    if any_found:
        print("[OK] Informacja nadal widoczna (co najmniej na jednym z adresów).")
        sys.exit(0)
    else:
        if errors:
            print("[WARN] Wystąpiły błędy podczas pobierania niektórych adresów:")
            for e in errors:
                print("       -", e)
        print("[ALERT] Informacja ZNIKNĘŁA (nie znaleziono na żadnym z adresów).")
        sys.exit(1)

if __name__ == "__main__":
    main()
