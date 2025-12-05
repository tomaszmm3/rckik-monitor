
# checker.py
# Reguła: OK tylko gdy (HTTP 200) AND (finalny URL == TARGET_URL) AND (treść zawiera uogólniony tytuł).
# W innym przypadku ALERT (exit 1). Problemy sieciowe -> exit 2 (bez maila).

import os
import sys
import time
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

TARGET_URL = os.getenv("TARGET_URL")
TEXT_TO_CHECK = os.getenv("TEXT_TO_CHECK")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}

def normalize_spaces(text: str) -> str:
    text = (text or "").replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def build_variants(base: str):
    # Uogólnione warianty dla dopasowania tytułu
    b = normalize_spaces(base).lower()
    variants = set()
    variants.add(b)
    variants.add(b.replace(" ab +", " ab+"))
    variants.add(b.replace(" ab+", " ab +"))
    # wariant bez plusa (na wypadek formatowania)
    variants.add(b.replace("+", "").replace("  ", " "))
    # wariant skrócony bez "dot." i bez końcówki (redukuje ryzyko braku przez skracanie tytułu)
    short = b.replace(" dot.", "").replace("  ", " ")
    variants.add(short)
    variants.add(short.replace(" ab +", " ab+"))
    variants.add(short.replace(" ab+", " ab +"))
    return variants

def fetch_follow(url: str, timeout: int = 30, max_hops: int = 5):
    """Pobierz stronę śledząc redirecty 3xx manualnie. Zwraca (final_response, history_list)."""
    current = url
    history = []
    for _ in range(max_hops):
        resp = requests.get(current, headers=HEADERS, timeout=timeout, allow_redirects=False)
        if not resp.encoding:
            resp.encoding = "utf-8"
        status = resp.status_code
        if 300 <= status < 400 and "Location" in resp.headers:
            nxt = resp.headers["Location"]
            if nxt.startswith("/"):
                nxt = urljoin(current, nxt)
            history.append((current, status, nxt))
            current = nxt
            continue
        return resp, history
    raise RuntimeError("Zbyt wiele przekierowań (pętla 3xx)")

def page_contains_text(resp_text: str, variants: set) -> bool:
    soup = BeautifulSoup(resp_text or "", "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)
    page_norm = normalize_spaces(page_text).lower()
    return any(v in page_norm for v in variants)

def same_url(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a.rstrip("/").lower() == b.rstrip("/").lower()

def main():
    if not TARGET_URL or not TEXT_TO_CHECK:
        print("[ERROR] Brak TARGET_URL lub TEXT_TO_CHECK w env.")
        sys.exit(2)

    print(f"[INFO] Sprawdzam URL: {TARGET_URL}")
    print(f"[INFO] Długość frazy do sprawdzenia: {len(TEXT_TO_CHECK)}")
    variants = build_variants(TEXT_TO_CHECK)
    print(f"[DEBUG] Liczba wariantów wzorca: {len(variants)}")

    # Pobierz stronę z manualnym śledzeniem 3xx
    try:
        final_resp, history = fetch_follow(TARGET_URL)
    except Exception as e:
        print(f"[ERROR] Błąd pobrania: {e}")
        sys.exit(2)

    if history:
        print("[DEBUG] Redirect chain:")
        for frm, st, to in history:
            print(f"        {st}: {frm} -> {to}")

    status = final_resp.status_code
    final_url = final_resp.url  # requests ustawia finalny URL nawet bez allow_redirects=True
    body = final_resp.text or ""
    length = len(body)

    print(f"[DEBUG] Final HTTP {status} | length={length} | final_url={final_url}")

    # Filar 1: HTTP 200
    if status != 200:
        if status in (404, 410):
            print(f"[ALERT] Artykuł zniknął (HTTP {status}).")
            sys.exit(1)
        else:
            print(f"[WARN] Niejednoznaczny status HTTP: {status}.")
            sys.exit(2)

    # Filar 2: finalny URL == TARGET_URL (eliminuje fałszywe 200 dla błędnych slugów)
    if not same_url(final_url, TARGET_URL):
        print("[ALERT] Finalny URL różni się od TARGET_URL – to nie jest dokładnie ten wpis.")
        sys.exit(1)

    # Filar 3: treść zawiera uogólniony tytuł (eliminuje przypadek innej treści pod właściwym adresem)
    found = page_contains_text(body, variants)
    print(f"[DEBUG] Dopasowanie treści: {'FOUND' if found else 'NOT_FOUND'}")

    if found:
        print("[OK] Artykuł nadal istnieje i zawiera oczekiwany tytuł.")
        sys.exit(0)
    else:
        print("[ALERT] Artykuł istnieje (HTTP 200 i URL poprawny), ale treść nie zawiera tytułu.")
        # W zależności od preferencji możesz tu zwrócić 2 (niejednoznaczne) zamiast 1
        sys.exit(1)

if __name__ == "__main__":
    main()
