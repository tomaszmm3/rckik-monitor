
import os, sys, time
import requests
from bs4 import BeautifulSoup

URL = os.getenv("TARGET_URL")
TEXT_TO_CHECK = os.getenv("TEXT_TO_CHECK")

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_with_retries(url, retries=2, timeout=30, backoff=3):
    last_exc = None
    for i in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
    raise last_exc

def main():
    if not URL or not TEXT_TO_CHECK:
        print("[ERROR] Brak TARGET_URL lub TEXT_TO_CHECK w env.")
        sys.exit(2)  # błąd konfiguracji, nie wysyłamy alertu

    print(f"[INFO] Sprawdzam: {URL}")
    # Uwaga: GitHub maskuje sekrety w logach, więc zobaczysz *** zamiast wartości
    print(f"[INFO] Szukam frazy (długość): {len(TEXT_TO_CHECK)}")

    try:
        resp = fetch_with_retries(URL)
    except Exception as e:
        print(f"[ERROR] Nie udało się pobrać strony: {e}")
        sys.exit(2)

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)

    if TEXT_TO_CHECK in page_text:
        print("[OK] Informacja nadal widoczna.")
        sys.exit(0)
    else:
        print("[ALERT] Informacja ZNIKNĘŁA!")
        sys.exit(1)

if __name__ == "__main__":
    main()
