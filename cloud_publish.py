"""Fiyat Avcısı: scheduled, serverless price collection for GitHub Pages.

Stores a compact JSON snapshot in the repository. A GitHub Actions job can run
this command, commit data/state.json and data/feed.json, and publish only the
static UI plus the public feed. Requires only Python's standard library.

No demonstration prices or API keys are ever written to the public feed.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from scanner import QUERY_BY_CATEGORY, ScanError, fetch_query, parse_offer

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data" / "state.json"
FEED_PATH = ROOT / "data" / "feed.json"
KEYBOARD_LIMIT = 1100
MOUSE_LIMIT = 1000
LIMITS = {"keyboard": KEYBOARD_LIMIT, "mouse": MOUSE_LIMIT}
CATEGORIES = tuple(QUERY_BY_CATEGORY)
STATE_SCHEMA = 1
FRESH_FOR_SECONDS = 48 * 3600
STALE_ENTRY_SECONDS = 120 * 86400
MAX_TRACKED_PRODUCTS = 900
MAX_HISTORY_POINTS = 36


def read_json(path: Path, fallback):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else fallback
    except (OSError, ValueError):
        return fallback


def empty_state():
    return {"schema": STATE_SCHEMA, "products": {}, "active": {category: [] for category in CATEGORIES},
            "last_success": None, "last_attempt": None, "last_warning": "", "last_error": ""}


def load_state(path: Path = STATE_PATH):
    # Existing/corrupted history is never replaced with an empty dataset.
    if not path.exists():
        return empty_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Durum dosyası okunamadı; geçmiş veriler korunuyor.") from exc
    if not isinstance(state, dict):
        raise ValueError("Durum dosyasının biçimi geçersiz; geçmiş veriler korunuyor.")
    if state.get("schema") != STATE_SCHEMA or not isinstance(state.get("products"), dict):
        raise ValueError("Desteklenmeyen durum verisi sürümü. Eski veriler otomatik silinmedi.")
    if not isinstance(state.get("active"), dict):
        state["active"] = {category: [] for category in CATEGORIES}
    for category in CATEGORIES:
        if not isinstance(state["active"].get(category), list):
            state["active"][category] = []
    return state


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def update_record(prior: dict | None, offer, now: int):
    if prior:
        record = dict(prior)
        old_price = float(record["price"])
        if abs(old_price - offer.price) >= 0.005:
            entries = list(record.get("history", []))
            entries.append([now, offer.price])
            record["history"] = entries[-MAX_HISTORY_POINTS:]
            record["last_change"] = now
            if offer.price < old_price:
                record["last_drop"] = now
                record["last_drop_from"] = old_price
            else:
                record["last_drop"] = None
                record["last_drop_from"] = None
        record["lowest_price"] = min(float(record.get("lowest_price", old_price)), offer.price)
        record["highest_price"] = max(float(record.get("highest_price", old_price)), offer.price)
    else:
        record = {"first_seen": now, "lowest_price": offer.price, "highest_price": offer.price,
                  "last_drop": None, "last_drop_from": None, "last_change": now,
                  "history": [[now, offer.price]]}
    record.update(id=offer.id, title=offer.title, store=offer.store, price=offer.price,
                  original_price=offer.original_price, link=offer.url, image=offer.image,
                  category=offer.category, connectivity=offer.connectivity, last_seen=now)
    return record


def scan_queries(key: str, fetcher=fetch_query):
    """Return successful category results, warning, total count and success count.

    Failed categories remain on their previous published snapshot. Partial search
    failures never falsely turn the whole site into '0 results'.
    """
    outcome = {}
    warnings = []
    raw_count = 0
    successful_queries = 0
    for category, queries in QUERY_BY_CATEGORY.items():
        matches = {}
        succeeded = 0
        for query in queries:
            try:
                rows = fetcher(key, query)
                succeeded += 1
                successful_queries += 1
                raw_count += len(rows)
                for row in rows:
                    offer = parse_offer(row, category=category)
                    if offer and (offer.id not in matches or offer.price < matches[offer.id].price):
                        matches[offer.id] = offer
            except ScanError:
                warnings.append(f"{category}: bir kaynak sorgusu yanıt vermedi")
        # Even a single successful query may yield an incomplete category. Keep a
        # union with last known active items in merge_scan when partial=True.
        outcome[category] = {"successes": succeeded, "total_queries": len(queries), "offers": list(matches.values())}
        if succeeded == 0:
            warnings.append(f"{category}: bu kategorideki sonuçlar güncellenemedi")
    return outcome, "; ".join(warnings), raw_count, successful_queries


def merge_scan(state: dict, result: dict, now: int):
    products = state["products"]
    active = state["active"]
    for category in CATEGORIES:
        detail = result[category]
        successes = detail["successes"]
        if successes == 0:
            continue
        new_ids = []
        for offer in detail["offers"]:
            if offer.id not in new_ids:
                new_ids.append(offer.id)
            products[offer.id] = update_record(products.get(offer.id), offer, now)
        if successes == detail["total_queries"]:
            active[category] = new_ids
        else:
            # Partial category refresh: don't falsely remove products only seen
            # in the failed query. Old items are clearly timestamped as such.
            active[category] = list(dict.fromkeys(new_ids + active.get(category, [])))
    state["last_success"] = now
    # Do not unboundedly grow state.json. Active entries are always retained.
    all_active = {product_id for ids in active.values() for product_id in ids}
    for identifier, row in list(products.items()):
        if identifier not in all_active and now - int(row.get("last_seen", 0)) > STALE_ENTRY_SECONDS:
            del products[identifier]
    if len(products) > MAX_TRACKED_PRODUCTS:
        inactive = sorted((r for i, r in products.items() if i not in all_active),
                          key=lambda r: int(r.get("last_seen", 0)))
        for row in inactive[:max(0, len(products) - MAX_TRACKED_PRODUCTS)]:
            products.pop(row["id"], None)
    return state


def public_feed(state: dict, configured: bool, now: int):
    items = []
    products = state.get("products", {})
    for category in CATEGORIES:
        for identifier in state.get("active", {}).get(category, []):
            row = products.get(identifier)
            if not row or row.get("category") != category:
                continue
            price = float(row.get("price") or 0)
            if price <= 0 or price > LIMITS[category]:
                continue
            last_drop = row.get("last_drop")
            drop_amount = (round(max(0.0, float(row.get("last_drop_from") or price) - price), 2)
                           if last_drop and now - int(last_drop) <= FRESH_FOR_SECONDS else 0)
            items.append({
                "id": identifier, "category": category, "title": row["title"],
                "store": row["store"], "price": price,
                "original_price": row.get("original_price"), "link": row.get("link", ""),
                "image": row.get("image", ""), "connectivity": row.get("connectivity", "unknown"),
                "first_seen": row["first_seen"], "last_seen": row["last_seen"],
                "lowest_price": row.get("lowest_price", price),
                "is_new": now - int(row["first_seen"]) <= FRESH_FOR_SECONDS,
                "drop_amount": drop_amount,
            })
    items.sort(key=lambda row: (row["category"] != "keyboard", row["price"], row["title"].casefold()))
    last_success = state.get("last_success")
    status = {
        "app": "Fiyat Avcısı", "public_site": True, "demo": False,
        "configured": configured, "scanning": False,
        "keyboard_max_price": KEYBOARD_LIMIT, "mouse_max_price": MOUSE_LIMIT,
        "last_success": last_success, "last_attempt": state.get("last_attempt"),
        "last_error": state.get("last_error", ""), "warning": state.get("last_warning", ""),
        "product_count": len(items),
        "stale": bool(last_success and now - int(last_success) > 36 * 3600),
        "scan_interval_minutes": None,
    }
    return {"schema": 1, "generated_at": now, "status": status, "products": items}


def run(state_path: Path = STATE_PATH, feed_path: Path = FEED_PATH,
        key: str = "", do_scan: bool = True, now: int | None = None, fetcher=fetch_query):
    now = int(now if now is not None else time.time())
    state = load_state(state_path)
    key = key.strip()
    if do_scan:
        state["last_attempt"] = now
        if not key:
            state["last_error"] = "Canlı tarama için GitHub Actions API anahtarı henüz eklenmedi."
        else:
            try:
                result, warning, total, completed = scan_queries(key, fetcher)
                if completed == 0:
                    raise ScanError("Ürün sağlayıcısından veri alınamadı; önceki sonuçlar korundu.")
                merge_scan(state, result, now)
                state["last_error"] = ""
                state["last_warning"] = warning
                state["last_raw_count"] = total
                state["last_completed_queries"] = completed
            except (ScanError, OSError, ValueError):
                state["last_error"] = "Ürün taraması başarısız oldu; önceki sonuçlar korunuyor. API anahtarını ve kotayı kontrol et."
    save_json(state_path, state)
    feed = public_feed(state, bool(key), now)
    save_json(feed_path, feed)
    return feed


def main():
    parser = argparse.ArgumentParser(description="GitHub Pages için Fiyat Avcısı JSON fiyat tarayıcısı")
    parser.add_argument("--no-scan", action="store_true", help="API kullanmadan kayıtlı veriden site JSON dosyası oluştur")
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    parser.add_argument("--feed", type=Path, default=FEED_PATH)
    args = parser.parse_args()
    key = os.getenv("SERPAPI_KEY", "")
    feed = run(state_path=args.state, feed_path=args.feed, key=key, do_scan=not args.no_scan)
    status = feed["status"]
    print(f"Fiyat Avcısı: {len(feed['products'])} uygun ürün; son başarılı tarama: {status['last_success'] or 'yok'}")
    if status["last_error"]:
        print(f"UYARI: {status['last_error']}")
    if status["warning"]:
        print(f"UYARI: {status['warning']}")


if __name__ == "__main__":
    main()
