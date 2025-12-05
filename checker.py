
import os, sys, time, re
import requests
from bs4 import BeautifulSoup

URL = os.getenv("TARGET_URL")
TEXT_TO_CHECK = os.getenv("TEXT_TO_CHECK")

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def fetch_with_retries(url, retries=2, timeout=30, backoff=3):
    last_exc = None
    for _ in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            # Wymuś poprawne kodowanie (czasem serwery nie ustawiają)
            if not resp.encoding:
                resp.encoding = "utf-8"
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
    raise last_exc

def normalize_spaces(text: str) -> str:
    # Zamiana niełamliwych spacji na zwykłe
    text = text.replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    # Redukcja wielokrotnych odstępów
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def build_patterns(base: str):
    """Zbuduj zestaw wariantów szukanej frazy (małe/duże litery, spacja przy '+')."""
    b = normalize_spaces(base)
    variants = set()
    # oryginał (lowercase)
    variants.add(b.lower())
    # wariant bez spacji przed plus
    variants.add(b.lower().replace(" ab +", " ab+"))
    # wariant ze spacją (na wszelki wypadek odwrotny kierunek)
    variants.add(b.lower().replace(" ab+", " ab +"))
    # dodatkowo usuń diakrytyki z samego AB + (tu akurat nie dotyczy, ale dla bezpieczeństwa)
    return variants

def main():
    if not URL or not TEXT_TO_CHECK:
        print("[ERROR] Brak TARGET_URL lub TEXT_TO_CHECK w env.")
        sys.exit(2)

    print(f"[INFO] Sprawdzam: {URL}")
    print(f"[INFO] Długość frazy do sprawdzenia: {len(TEXT_TO_CHECK)}")

    try:
        resp = fetch_with_retries(URL)
    except Exception as e:
        print(f"[ERROR] Nie udało się pobrać strony: {e}")
        sys.exit(2)

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)
    page_norm = normalize_spaces(page_text).lower()

    patterns = build_patterns(TEXT_TO_CHECK)

    found_any = any(p in page_norm for p in patterns)
    print(f"[DEBUG] Liczba wariantów wzorca: {len(patterns)}")
    print(f"[DEBUG] Wynik wyszukiwania: {'FOUND' if found_any else 'NOT_FOUND'}")

    # (Opcjonalnie na czas debugowania) pokaż pierwszych 500 znaków
    # print("[DEBUG] Fragment treści:", page_norm[:500])

    if found_any:
        print("[OK] Informacja nadal widoczna.")
        sys.exit(0)
    else:
        print("[ALERT] Informacja ZNIKNĘŁA!")
        sys.exit(1)

if __name__ == "__main__":
    main()
