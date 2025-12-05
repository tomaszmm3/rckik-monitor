
# checker.py
# Monitor "status + canonical": alert tylko, gdy DOKŁADNY adres przestaje być dostępny
# lub canonical już nie wskazuje na ten adres.

import os
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

URL = os.getenv("TARGET_URL")  # np. https://rckik.krakow.pl/aktualnosci/komunikat-dot-pobierania-krwi-w-grupie-ab

HEADERS = {
    # Solidny UA zmniejsza ryzyko blokad po stronie serwera
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
}

def fetch_once(url: str, timeout: int = 30) -> requests.Response:
    """
    Pobierz stronę BEZ automatycznych redirectów, aby zobaczyć faktyczny status i Location.
    """
    resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=False)
    if not resp.encoding:
        resp.encoding = "utf-8"
    return resp

def follow_redirects(url: str, timeout: int = 30, max_hops: int = 5):
    """
    (Opcjonalne) Ręczne śledzenie redirectów 3xx, by dojść do finalnej strony i
    odczytać <link rel="canonical">/og:url. Zwraca (final_response, history_list).
    history_list: list[ (from_url, status, to_url) ]
    """
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
    raise RuntimeError("Zbyt wiele przekierowań (podejrzana pętla 3xx).")

def extract_canonical(resp_text: str):
    """
    Zwraca adres z ... lub z <meta property="og:url">.
    """
    soup = BeautifulSoup(resp_text or "", "html.parser")
    link = soup.select_one("link[rel=canonical][href]")
    if link and link.get("href"):
        return link["href"].strip()
    meta = soup.select_one("meta[property='og:url'][content]")
    if meta and meta.get("content"):
        return meta["content"].strip()
    return None

def same_url(a: str, b: str) -> bool:
    """
    Porównanie adresów z pominięciem końcowego slasha.
    (W razie potrzeby można rozszerzyć o normalizację http/https, www itp.)
    """
    if not a or not b:
        return False
    return a.rstrip("/").lower() == b.rstrip("/").lower()

def main():
    if not URL:
        print("[ERROR] Brak TARGET_URL w env.")
        sys.exit(2)

    print(f"[INFO] Sprawdzam URL: {URL}")

    # 1) Pobranie bez redirectów
    try:
        resp0 = fetch_once(URL)
    except Exception as e:
        print(f"[ERROR] Błąd pobrania (bez redirectów): {e}")
        # Nie wysyłamy alertu przy problemach sieciowych – runner spróbuje ponownie zgodnie z harmonogramem
        sys.exit(2)

    status0 = resp0.status_code
    length0 = len(resp0.text or "")
    loc0 = resp0.headers.get("Location")
    print(f"[DEBUG] Wstępny HTTP {status0} | length={length0} | Location={loc0}")

    # 3xx: URL nie odpowiada bezpośrednio -> traktuj jako brak tego KONKRETNEGO wpisu
    if 300 <= status0 < 400:
        print("[ALERT] 3xx (redirect) na monitorowanym URL – to już nie jest dokładnie ten adres.")
        sys.exit(1)

    # 404/410: jednoznacznie zniknął
    if status0 in (404, 410):
        print(f"[ALERT] Artykuł zniknął (HTTP {status0}).")
        sys.exit(1)

    # 200: sprawdź canonical/og:url – musi wskazywać dokładnie na TARGET_URL
    if status0 == 200:
        canonical0 = extract_canonical(resp0.text)
        print(f"[DEBUG] canonical={canonical0}")
        if canonical0 and same_url(canonical0, URL):
            print("[OK] Artykuł istnieje (HTTP 200, canonical == TARGET_URL).")
            sys.exit(0)

        # Jeśli canonical nie zgadza się – sprawdź jeszcze finalną stronę po ewentualnych kaskadach 3xx
        # (gdyby serwis bawił się w niestandardowe przekierowania).
        try:
            final_resp, history = follow_redirects(URL)
            statusF = final_resp.status_code
            lengthF = len(final_resp.text or "")
            canonicalF = extract_canonical(final_resp.text)
            # Krótkie logi historii przekierowań (jeśli były)
            if history:
                print("[DEBUG] Redirect chain:")
                for frm, st, to in history:
                    print(f"        {st}: {frm} -> {to}")
            print(f"[DEBUG] Final HTTP {statusF} | length={lengthF} | canonical_final={canonicalF}")

            if statusF == 200 and canonicalF and same_url(canonicalF, URL):
                print("[OK] Artykuł istnieje (HTTP 200 po ścieżce, canonical == TARGET_URL).")
                sys.exit(0)
            else:
                print("[ALERT] HTTP 200, ale canonical != TARGET_URL – to nie jest dokładnie ten wpis.")
                sys.exit(1)

        except Exception as e:
            print(f"[WARN] Problem podczas śledzenia redirectów: {e}")
            print("[ALERT] Nie udało się potwierdzić canonical == TARGET_URL.")
            sys.exit(1)

    # Inne statusy (np. 5xx/403/401) – niejednoznaczne, bez alertu
    print(f"[WARN] Niejednoznaczny status HTTP: {status0} (bez redirectów).")
    sys.exit(2)

if __name__ == "__main__":
    main()
