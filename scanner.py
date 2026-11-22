"""Google Shopping and Google Product offers via SerpApi.

Compare *observed* seller offers for the same model. Never claim every retailer
was checked. Unknown sensors and unsupported currencies are not guessed.
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

from merchants import trusted_retailer

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
    sensor: str = ""
    product_id: str = ""
    model_key: str = ""


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


def detect_mouse_sensor(text: str) -> str:
    """Accept only a sensor designation explicitly stated in supplier text.

    Never infer a sensor merely from a mouse brand/model or DPI rating.
    """
    text = clean_text(text)
    patterns = (
        (r"\b(?:pixart\s*)?(paw|pmw|adns|a3090)[\s-]*(\d{3,5}[a-z]?)\b", 'pixart'),
        (r"\b(hero)[\s-]*(\d{1,2}k)\b", 'hero'),
        (r"\b(truemove)[\s-]*(air|pro|3|3\+|core)\b", 'truemove'),
    )
    for pattern, kind in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        if kind == 'pixart':
            return (match.group(1) + match.group(2)).upper()
        if kind == 'hero':
            return (match.group(1) + ' ' + match.group(2)).upper()
        return 'TRUEMOVE ' + match.group(2).upper()
    if re.search(r"\bfocus[ -]?pro[ -]?(?:30k|35k)?\b", text):
        match = re.search(r"\bfocus[ -]?pro[ -]?(30k|35k)?\b", text)
        return 'FOCUS PRO' + (' ' + match.group(1).upper() if match.group(1) else '')
    return ''


# A whitelist by measured sensor family rather than a numerical comparison:
# PAW3327 (220 IPS) is not above PAW3311 (300 IPS), despite the larger number.
# Unlisted/unknown models remain hidden, to avoid misleading shoppers.
ELIGIBLE_SENSORS = frozenset({
    "PAW3311", "PAW3315", "PAW3333", "PAW3335", "PAW3370", "PAW3395",
    "PAW3399", "PAW3950", "PAW3955", "PMW3360", "PMW3366", "PMW3389",
    "PMW3391", "PMW3399",
})
BRANDS = (
    "james donkey", "logitech", "steelseries", "gamepower", "magegee", "redragon",
    "hyperx", "razer", "ajazz", "aula", "fantech", "attack shark", "delux",
    "pulsar", "asus", "msi", "inca", "rampage", "hawkgaming", "hawk gaming",
    "claw's", "claws", "keychron", "monster", "lenovo", "hp",
)
MODEL_SKIP_PREFIXES = {"paw", "pmw", "adns", "rgb", "dpi", "usb", "bt", "ghz", "mah", "hz"}


def sensor_is_eligible(sensor: str) -> bool:
    return re.sub(r"[^A-Z0-9]", "", (sensor or "").upper()) in ELIGIBLE_SENSORS


def model_sensor_from_verified_catalog(title: str) -> str:
    """Only exact previously verified model names, never marketing DPI or number heuristics.

    Model catalog is deliberately small; other models need an explicit sensor
    in the provider metadata to meet the user's PAW3311+ condition.
    """
    t = clean_text(title)
    if re.search(r"\bjames[ -]?donkey\s+jdm11\b", t):
        return "PAW3311"
    if re.search(r"\bmagegee\s+scout\b", t):
        return "PAW3311"
    return ""


def validated_sensor(title: str, details: str = "") -> str:
    return detect_mouse_sensor(f"{title} {details}") or model_sensor_from_verified_catalog(title)


def candidate_from_shopping_row(row: dict, category: str) -> Offer | None:
    """Unverified private candidate for Google Product detail lookup.

    The Shopping result may point to Google instead of a seller. Such a row
    must NEVER be placed in the public feed; only a seller detail with an
    approved direct HTTPS merchant URL can become a real Offer.
    """
    if not isinstance(row, dict) or category not in QUERY_BY_CATEGORY:
        return None
    title = str(row.get("title") or "").strip()[:220]
    if not (is_keyboard(title) if category == "keyboard" else is_mouse(title)):
        return None
    product_id = str(row.get("product_id") or "").strip()
    if not re.fullmatch(r"\d{8,22}", product_id):
        return None
    price_raw = row.get("price")
    if isinstance(price_raw, str) and re.search(r"(?:\$|€|£|\b(?:USD|EUR|GBP)\b)", price_raw, re.I) and not re.search(r"(?:₺|\b(?:TL|TRY)\b)", price_raw, re.I):
        return None
    price = parse_price(row.get("extracted_price")) or parse_price(price_raw)
    if price is None or price > 5000:
        return None
    if row.get("extracted_price") is not None and price_raw is not None:
        displayed = parse_price(price_raw)
        if displayed is not None and abs(displayed-price) > max(2, price * 0.03):
            return None
    if isinstance(price_raw, str) and re.search(r"\b(taksit|ayda|aylik|monthly|installment)\b", clean_text(price_raw)):
        return None
    title_info = str(row.get("snippet") or row.get("description") or "")
    sensor = validated_sensor(title, title_info) if category == "mouse" else ""
    image = safe_https(row.get("thumbnail")) or safe_https(row.get("serpapi_thumbnail"))
    return Offer(f"private:{product_id}", title, str(row.get("source") or ""), price,
                 None, "", image, category, detect_connectivity(title), sensor,
                 product_id, product_model_key(title, category, product_id))


def product_model_key(title: str, category: str, product_id: str = "") -> str:
    """Conservative model-identity matcher. Same brand+model, not just 'gaming mouse'.

    Prevents JDK87 being merged with JDK99 and different brands' G102-like
    model codes being merged. Products with no reliable code need exact titles.
    """
    t = clean_text(title)
    brand = next((b for b in BRANDS if re.search(r"(?<![a-z])" + re.escape(b) + r"(?![a-z])", t)), "")
    codes = re.findall(r"(?<![a-z0-9])([a-z]{1,10}[ -]?\d{1,5}[a-z0-9]{0,3})(?![a-z0-9])", t)
    codes = [re.sub(r"[ -]", "", c) for c in codes if re.match(r"[a-z]+", c).group() not in MODEL_SKIP_PREFIXES]
    # Brand must be known to avoid grouping unrelated generic listings.
    if brand and codes:
        return f"{category}|{brand}|{codes[0]}"
    # If a Google product_id is shared across listings it is a safer fallback.
    if product_id and re.fullmatch(r"\d{8,22}", product_id):
        return f"{category}|google|{product_id}"
    normalized = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return f"{category}|exact|{normalized}"


PRICE_COMPARISON_SOURCES = (
    "akakce", "epey", "cimri", "enucuzsistem", "eniyipc", "bozukluk", "secmatik"
)


def is_comparison_only(store: str, url: str) -> bool:
    """Don't mistake a price-comparison page for an actual store offer."""
    name = re.sub(r"[^a-z0-9]+", "", clean_text(store))
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    return any(source in name or host == source + ".com" or host.endswith("." + source + ".com")
               or host == source + ".com.tr" or host.endswith("." + source + ".com.tr")
               for source in PRICE_COMPARISON_SOURCES)


def direct_merchant_link(row: dict) -> str:
    """Prefer merchant link, not Google's generic product page."""
    first_https = ""
    for field in ("link", "product_link"):
        url = safe_https(row.get(field))
        if not url:
            continue
        if trusted_retailer(url):
            return url
        if not first_https:
            first_https = url
    return first_https


def is_google_comparison_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == "google.com" or host.endswith(".google.com") or host == "google.com.tr" or host.endswith(".google.com.tr")


def parse_product_stores(payload: dict, original: Offer) -> list[Offer]:
    """Extract matching merchant offers from SerpApi Google Product API data.

    Do not merge unrelated variants or secondhand/refurbished offers.
    """
    result = payload.get("product_results") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return []
    # A product's canonical Google detail title may state the sensor even when
    # the Shopping search card / seller title does not. Require same model key.
    if original.category == "mouse" and not sensor_is_eligible(original.sensor):
        product_title = str(result.get("title") or "")
        if product_title and product_model_key(product_title, "mouse") == original.model_key:
            canonical_sensor = validated_sensor(product_title)
            if sensor_is_eligible(canonical_sensor):
                from dataclasses import replace
                original = replace(original, sensor=canonical_sensor)
    store_rows = result.get("stores", [])
    if not isinstance(store_rows, list):
        return []
    offers = []
    for item in store_rows:
        if not isinstance(item, dict):
            continue
        condition = clean_text(item.get("condition", ""))
        if any(x in condition for x in ("used", "refurbished", "second hand", "yenilenmis", "ikinci el")):
            continue
        title = str(item.get("title") or original.title)
        store = str(item.get("name") or "").strip()
        if not store or not direct_merchant_link(item):
            continue
        if product_model_key(title, original.category) != product_model_key(original.title, original.category):
            # Google can group variants; do not merge different product models.
            continue
        # Store titles sometimes omit "gaming" or "mouse" even when brand+model
        # match the validated Shopping product. Reuse the complete parent title
        # ONLY after confirming identical brand+model key.
        parsed_title = title
        if original.category == "mouse" and not is_mouse(title):
            parsed_title = original.title
        if original.category == "keyboard" and not is_keyboard(title):
            parsed_title = original.title
        row = dict(title=parsed_title, source=store, price=item.get("price"),
                   extracted_price=item.get("extracted_price"),
                   product_link=item.get("link"), link=item.get("link"),
                   thumbnail=original.image, description=original.sensor)
        offer = parse_offer(row, category=original.category)
        if offer and not is_google_comparison_url(offer.url):
            if original.category == 'mouse' and not sensor_is_eligible(offer.sensor):
                # Product-details store titles often omit sensor; verified original sensor.
                if sensor_is_eligible(original.sensor):
                    from dataclasses import replace
                    offer = replace(offer, sensor=original.sensor)
                else:
                    continue
            offers.append(offer)
    return offers


def fetch_product_stores(api_key: str, product_id: str, timeout: int = 22) -> dict:
    """One quota-consuming SerpApi lookup; never call directly from the browser."""
    if not re.fullmatch(r"\d{8,22}", str(product_id)):
        return {}
    params = urlencode({"engine": "google_product", "product_id": product_id,
                        "gl": "tr", "hl": "tr", "api_key": api_key})
    request = Request(f"{API_URL}?{params}", headers={"Accept": "application/json", "User-Agent": "FiyatAvcisi/2.5"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ScanError(f"Ürün mağazaları alınamadı ({type(exc).__name__}).") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise ScanError("Ürün mağaza sorgusu reddedildi.")
    return payload


def fetch_remaining_quota(api_key: str, timeout: int = 15) -> int | None:
    """Free account endpoint; fail closed for extra lookups when unreachable."""
    request = Request("https://serpapi.com/account.json?" + urlencode({"api_key": api_key}),
                      headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        amount = data.get("total_searches_left", data.get("plan_searches_left"))
        return int(amount) if isinstance(amount, (int, float)) and amount >= 0 else None
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        return None


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
    return has_mouse and gaming and not (any(x in t for x in excluded if x not in ('mouse kablosu', 'fare kablosu')) or bool(re.search(r'\b(?:mouse|fare) kablosu\b', t)))


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


def parse_offer(row: dict, tracking_limit: float = 999999, category: str = "keyboard") -> Offer | None:
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
    url = direct_merchant_link(row)
    store = trusted_retailer(url)
    # Price and merchant must refer to the approved store's real HTTPS domain.
    # Source text (e.g. a Google Shopping merchant display name) is not proof.
    if not store or is_comparison_only(str(row.get("source") or ""), url):
        return None
    # SerpApi may occasionally mix a summary price with another price field.
    # Reject contradictory prices rather than falsely advertising a discount.
    if row.get("price") is not None and row.get("extracted_price") is not None:
        displayed = parse_price(row.get("price"))
        extracted = parse_price(row.get("extracted_price"))
        if displayed is not None and extracted is not None and abs(displayed-extracted) > max(2, extracted*0.03):
            return None
    if isinstance(price_raw, str) and re.search(r"\b(?:taksit|ayda|aylik|monthly|installment)\b", clean_text(price_raw)):
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
    details = row.get('description') or row.get('snippet') or ''
    if not isinstance(details, str):
        details = ''
    sensor = validated_sensor(title, details) if category == 'mouse' else ''
    if category == "mouse" and not sensor_is_eligible(sensor):
        return None
    return Offer(offer_id, title, store, price, original_price, url, image, category,
                 detect_connectivity(title), sensor, product_id,
                 product_model_key(title, category, product_id))


class ScanError(Exception):
    pass


def fetch_query(api_key: str, query: str, timeout: int = 22) -> list[dict]:
    params = urlencode({
        "engine": "google_shopping",
        "q": query,
        "gl": "tr",
        "hl": "tr",
        "google_domain": "google.com.tr",
        # Sorting in the provider helps surface low-priced models that are
        # otherwise buried under sponsored/popular shopping results.
        "sort_by": "1",
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
