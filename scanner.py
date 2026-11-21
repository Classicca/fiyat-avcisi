"""Google Shopping discovery through SerpApi. No direct store scraping.

The API can return irrelevant/non-TRY results, so all offers are verified locally.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

QUERY_BY_CATEGORY = {
    "keyboard": (
        "kablosuz gaming klavye",
        "kablolu gaming klavye",
    ),
    "mouse": (
        "kablolu gaming mouse",
        "kablosuz gaming mouse",
    ),
}
SEARCH_QUERIES = tuple((category, query) for category, queries in QUERY_BY_CATEGORY.items() for query in queries)

API_URL = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class Offer:
    id: str
    title: str
    store: str
    price: float
    original_price: float | None
    url: str
    image: str
    category: str = "keyboard"
    connectivity: str = "unknown"


def clean_text(text: str) -> str:
    text = str(text or "").casefold().replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def parse_price(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        p = float(value)
        return round(p, 2) if 0 < p < 1000000 else None
    s = str(value).strip()
    match = re.search(r"\d[\d.,\s]*", s)
    if not match:
        return None
    s = re.sub(r"\s", "", match.group()).rstrip(".,")
    if not s:
        return None
    if "," in s and "." in s:
        decimal = "," if s.rfind(",") > s.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        s = s.replace(thousands, "").replace(decimal, ".")
    elif "," in s or "." in s:
        separator = "," if "," in s else "."
        chunks = s.split(separator)
        if len(chunks) == 2 and 1 <= len(chunks[1]) <= 2:
            s = chunks[0] + "." + chunks[1]
        else:
            s = "".join(chunks)
    try:
        p = float(s)
        return round(p, 2) if 0 < p < 1000000 else None
    except ValueError:
        return None


def detect_connectivity(title: str) -> str:
    """Classify only when the product title gives clear evidence. Dual-mode devices match both filters."""
    t = clean_text(title)
    wireless = bool(re.search(r"\b(kablosuz|wireless|bluetooth|blu tooth|bluetoothlu|dongle|2[.,]4\s*(?:g|ghz)|tri[ -]?mode|trimode)\b", t))
    wired = bool(re.search(r"\b(kablolu|wired|corded|wire[ -]?connected)\b", t))
    if wireless and wired:
        return "both"
    if wireless:
        return "wireless"
    if wired:
        return "wired"
    return "unknown"


def is_keyboard(title: str) -> bool:
    t = clean_text(title)
    has_keyboard = any(word in t for word in ("klavye", "keyboard"))
    has_gaming = any(word in t for word in (
        "gaming", "oyuncu", "mekanik", "mechanical", "rgb"
    ))
    excluded = (
        "keycap", "key caps", "tus basligi", "tus seti", "switch seti", "klavye kilifi",
        "klavye koruyucu", "klavye sticker", "klavye etiketi", "keyboard cover",
        "keyboard case", "keyboard stand", "klavye standi", "klavye bilek destegi",
        "klavye mouse set", "klavye fare set", "keyboard mouse combo", "keyboard and mouse combo",
        "klavye temizleme", "keyboard cleaning", "klavye kablosu", "keyboard cable",
        "mini keypad", "numpad", "sayi tus takimi", "keypad", "mouse pad", "mousepad",
    )
    return has_keyboard and has_gaming and not any(x in t for x in excluded)


def is_mouse(title: str) -> bool:
    """Select gaming mice, excluding mousepads, accessories and office models.

    Both wired and wireless gaming mice are eligible.
    """
    t = clean_text(title)
    has_mouse = bool(re.search(r"(?<![a-z])(mouse|fare|mice)(?![a-z])", t))
    gaming = any(word in t for word in (
        "gaming", "oyuncu", "e-spor", "espor", "esports", "rgb", "dpi",
        "fps mouse", "fps fare", "ultralight", "ultra light", "hafif oyuncu",
        "pixart", "lightsync", "razer", "steelseries", "hyperx", "logitech g",
        "gamepower", "rampage", "deathadder", "viper", "g pro",
    ))
    excluded = (
        "mousepad", "mouse pad", "mouse mat", "mouse matı", "mouse altligi",
        "fare altligi", "mouse skate", "mouse feet", "mouse grip", "mouse bant",
        "fare pedi", "fare pad", "bilek destek", "mouse bungee", "mouse kablosu",
        "fare kablosu", "mouse switch", "mouse sensor", "mouse cover",
        "mouse case", "mouse kılıf", "mouse kilif", "yedek parca",
        "temizlik seti", "keyboard", "klavye", "mouse seti", "fare seti",
        "mouse combo", "fare combo", "mouse +", "mouse &", "mouse and",
        "klavye mouse", "klavye fare", "trackball", "touchpad", "gamepad",
        "mouse dongle", "mouse adaptoru", "mouse receiver", "mouse alici",
        "fare alici", "mouse sticker", "fare sticker",
    )
    return has_mouse and gaming and not any(x in t for x in excluded)


def safe_https(url) -> str:
    if not isinstance(url, str):
        return ""
    url = url.strip()
    if len(url) > 3000:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    return url


def parse_offer(row: dict, tracking_limit: float = 5000, category: str = "keyboard") -> Offer | None:
    if not isinstance(row, dict):
        return None
    title = str(row.get("title") or "").strip()[:220]
    if category not in QUERY_BY_CATEGORY:
        return None
    if not (is_keyboard(title) if category == "keyboard" else is_mouse(title)):
        return None
    price_raw = row.get("price")
    # Prevent accidentally treating an explicitly foreign-currency price as TRY.
    if isinstance(price_raw, str) and (any(c in price_raw for c in ("$", "€", "£")) or re.search(r"\b(?:USD|EUR|GBP)\b", price_raw, re.I)) and not any(
        c in price_raw for c in ("₺", "TL", "TRY")
    ):
        return None
    price = parse_price(row.get("extracted_price")) or parse_price(price_raw)
    if price is None or price > tracking_limit:
        return None
    store = str(row.get("source") or "Bilinmeyen mağaza").strip()[:100]
    url = safe_https(row.get("product_link")) or safe_https(row.get("link"))
    if not url:
        return None
    original_price = parse_price(row.get("extracted_old_price")) or parse_price(row.get("old_price"))
    if original_price is not None and original_price <= price:
        original_price = None
    image = safe_https(row.get("thumbnail")) or safe_https(row.get("serpapi_thumbnail"))
    product_id = str(row.get("product_id") or "").strip()
    normalized_title = re.sub(r"[^a-z0-9]+", " ", clean_text(title)).strip()
    # Product ID (when available) lets title changes keep the same price history.
    identity = f"{category}|{clean_text(store)}|{product_id or normalized_title}"
    offer_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return Offer(offer_id, title, store, price, original_price, url, image, category, detect_connectivity(title))


class ScanError(Exception):
    pass


def fetch_query(api_key: str, query: str, timeout: int = 22) -> list[dict]:
    params = urlencode({
        "engine": "google_shopping",
        "q": query,
        "gl": "tr",
        "hl": "tr",
        "google_domain": "google.com.tr",
        "api_key": api_key,
    })
    req = Request(f"{API_URL}?{params}", headers={"Accept": "application/json", "User-Agent": "FiyatAvcisi/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise ScanError(f"Veri sağlayıcısı HTTP {exc.code} hatası döndürdü. API anahtarını ve kotayı kontrol et.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise ScanError(f"Veri sağlayıcısına ulaşılamadı ({type(exc).__name__}).") from exc
    if not isinstance(data, dict):
        raise ScanError("Veri sağlayıcısından beklenmeyen yanıt alındı.")
    if data.get("error"):
        # The API error may contain a URL with an api_key. Never echo the untrusted message.
        raise ScanError("SerpApi isteği reddetti. API anahtarını, aboneliğini ve kullanım kotanı kontrol et.")
    results = data.get("shopping_results", [])
    if not isinstance(results, list):
        raise ScanError("Ürün verileri beklenen formatta değil.")
    return results


def collect_offers(api_key: str, queries=SEARCH_QUERIES, fetcher=fetch_query):
    """Return offers, total raw results and a warning for partial failures.

    Does not silently accept complete failure as an empty successful scan.
    """
    result_by_id = {}
    failures = []
    raw_count = 0
    successes = 0
    for entry in queries:
        category, query = entry if isinstance(entry, tuple) else ("keyboard", entry)
        try:
            rows = fetcher(api_key, query)
            successes += 1
            raw_count += len(rows)
            for row in rows:
                offer = parse_offer(row, category=category)
                if offer and (offer.id not in result_by_id or offer.price < result_by_id[offer.id].price):
                    result_by_id[offer.id] = offer
        except ScanError as exc:
            failures.append(str(exc))
    if not successes:
        raise ScanError(failures[0] if failures else "Ürün taraması başarısız.")
    warning = f"{len(failures)} arama tamamlanamadı. Sonuçlar eksik olabilir." if failures else ""
    return list(result_by_id.values()), raw_count, warning
