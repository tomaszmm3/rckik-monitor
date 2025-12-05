
import os, sys, time
import requests

URL = os.getenv("TARGET_URL")  # Ustaw: https://rckik.krakow.pl/aktualnosci/komunikat-dot-pobierania-krwi-w-grupie-ab

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def fetch_with_retries(url, retries=2, timeout=30, backoff=3):
    last_exc = None
    for _ in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            # Jeśli serwer nie zwraca encoding, wymuś utf-8
            if not resp.encoding:
                resp.encoding = "utf-8"
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
    raise last_exc

def main():
    if not URL:
        print("[ERROR] Brak TARGET_URL w env.")
        sys.exit(2)

    print(f"[INFO] Sprawdzam URL: {URL}")
    try:
        resp = fetch_with_retries(URL)
    except Exception as e:
        print(f"[ERROR] Błąd pobrania: {e}")
        # Nie wysyłamy alertu przy problemach sieciowych; lepiej powtórzyć za 5 min
        sys.exit(2)

    status = resp.status_code
    final_url = resp.url
    length = len(resp.text or "")
    print(f"[DEBUG] HTTP {status} | length={length} | final_url={final_url}")

    # Kryteria obecności:
    #  - 200 => artykuł istnieje (OK)
    #  - 404/410 => artykuł nie istnieje (ALERT)
    #  - Inne kody (3xx/5xx) => niejednoznaczne (exit 2, bez alertu)
    if status == 200:
        print("[OK] Artykuł nadal istnieje (HTTP 200).")
        sys.exit(0)
    elif status in (404, 410):
        print("[ALERT] Artykuł zniknął (HTTP 404/410).")
        sys.exit(1)
    else:
        print(f"[WARN] Niejednoznaczny status HTTP: {status}.")
        sys.exit(2)

if __name__ == "__main__":
    main()
