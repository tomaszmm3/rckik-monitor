
import os, sys, time, re
import requests
from bs4 import BeautifulSoup

PRIMARY_URL = os.getenv("TARGET_URL")  # np. https://rckik.krakow.pl/aktualnosci
TEXT_TO_CHECK = os.getenv("TEXT_TO_CHECK")  # np. Komunikat dot. pobierania krwi w grupie AB +

ARTICLE_URL = "https://rckik.krakow.pl/aktualnosci/komunikat-dot-pobierania-krwi-w-grupie-ab"
FALLBACK_URLS = [
    "https://rckik.krakow.pl/",
    ARTICLE_URL,
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def fetch_with_retries(url, retries=2, timeout=30, backoff=3):
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if not resp.encoding:
                resp.encoding = "utf-8"
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            time.sleep(backoff)
    raise last_exc

def normalize_spaces(text: str) -> str:
    text = (text or "").replace("\u00A0", " ").replace("\u2007", " ").replace("\u202F", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def build_variants(base: str):
    b = normalize_spaces(base).lower()
    variants = set()
    variants.add(b)
    variants.add(b.replace(" ab +", " ab+"))
    variants.add(b.replace(" ab+", " ab +"))
    # Dodatkowy wariant bez znaku '+' (czasem CMS kroi tytuł)
    variants.add(b.replace("+", "").replace("  ", " "))
    return variants

def page_contains_text(resp_text: str, variants: set) -> bool:
    soup = BeautifulSoup(resp_text, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)
    page_norm = normalize_spaces(page_text).lower()
    return any(v in page_norm for v in variants)

def check_url_for_text(url: str, variants: set):
    try:
        resp = fetch_with_retries(url)
        body = resp.text or ""
        found = page_contains_text(body, variants)
        print(f"[DEBUG] URL: {url} | HTTP {resp.status_code} | length={len(body)} | {'FOUND' if found else 'NOT_FOUND'}")
        return resp.status_code, found
    except requests.HTTPError as he:
        status = getattr(he.response, "status_code", "N/A")
        print(f"[DEBUG] URL: {url} | HTTP {status} | exception={he}")
        return status, False
    except Exception as e:
        print(f"[DEBUG] URL: {url} | exception={e}")
        return "ERR", False

def main():
    if not PRIMARY_URL or not TEXT_TO_CHECK:
        print("[ERROR] Brak TARGET_URL lub TEXT_TO_CHECK w env.")
        sys.exit(2)

    print(f"[INFO] Główny adres: {PRIMARY_URL}")
    print(f"[INFO] Długość frazy do sprawdzenia: {len(TEXT_TO_CHECK)}")

    variants = build_variants(TEXT_TO_CHECK)
    print(f"[DEBUG] Liczba wariantów wzorca: {len(variants)}")

    urls = [PRIMARY_URL] + FALLBACK_URLS

    status_article, found_article = check_url_for_text(ARTICLE_URL, variants)
    # Filar A: obecność artykułu = HTTP 200 na podstronie artykułu
    article_exists = (status_article == 200)

    found_any = found_article
    for u in urls:
        status, found = check_url_for_text(u, variants)
        found_any = found_any or found

    if article_exists or found_any:
        print("[OK] Informacja nadal widoczna (HTTP200 lub dopasowanie tekstu).")
        sys.exit(0)
    else:
        print("[ALERT] Informacja ZNIKNĘŁA (brak HTTP200 oraz brak dopasowania tekstu).")
        sys.exit(1)

if __name__ == "__main__":
    main()
