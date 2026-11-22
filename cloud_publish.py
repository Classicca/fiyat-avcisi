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

from discovery import choose_discovery_queries
from merchants import trusted_retailer, APPROVED_RETAILERS
from scanner import (QUERY_BY_CATEGORY, ScanError, fetch_query, parse_offer,
                     fetch_product_stores, fetch_remaining_quota, parse_product_stores,
                     product_model_key, sensor_is_eligible, is_google_comparison_url,
                     candidate_from_shopping_row)

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
VISIBLE_OFFER_SECONDS = 10 * 86400  # Recently discovered offers; old ones are removed.
MAX_TRACKED_PRODUCTS = 900
MAX_HISTORY_POINTS = 36
# Free SerpApi plan: 250 calls/month. One nightly run: 4 discovery + 1 focused
# search + at most 2 product seller lookups = up to 217 calls in a 31-day month.
MIN_EXTRA_CREDIT_RESERVE = 30
MAX_STORE_LOOKUPS = 1


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
                  category=offer.category, connectivity=offer.connectivity, sensor=offer.sensor,
                  product_id=offer.product_id, model_key=offer.model_key, last_seen=now)
    return record


def scan_queries(key: str, fetcher=fetch_query, *, focus_query=None, focus_queries=None,
                 product_fetcher=fetch_product_stores, max_product_details=0,
                 checked_product_ids=None, now=0):
    """Collect matched offers from broad and focused searches plus seller pages.

    A seller detail request is performed for at most max_product_details Google
    product IDs; it is quota-limited at the caller. Failures preserve previous data.
    """
    outcome, warnings, raw_count, successful_queries = {}, [], 0, 0
    plan = {category: list(queries) for category, queries in QUERY_BY_CATEGORY.items()}
    for entry in ([focus_query] if focus_query else []) + list(focus_queries or ()):
        if entry[0] in plan and entry[1] not in plan[entry[0]]:
            plan[entry[0]].append(entry[1])
    candidates = {}
    focused_product_ids = set()
    diagnostics = {"raw": 0, "direct_approved": 0,
                   "detail_candidates": 0, "indirect_candidates": 0,
                   "details_checked": 0, "details_verified_offers": 0}
    focused_terms = {(category, query) for category, query in ([focus_query] if focus_query else []) + list(focus_queries or ())}
    for category, queries in plan.items():
        matches = {}
        succeeded = 0
        for query in queries:
            try:
                rows = fetcher(key, query)
                succeeded += 1
                successful_queries += 1
                raw_count += len(rows)
                for row in rows:
                    diagnostics["raw"] += 1
                    offer = parse_offer(row, category=category)
                    if offer:
                        diagnostics["direct_approved"] += 1
                        if offer.id not in matches or offer.price < matches[offer.id].price:
                            matches[offer.id] = offer
                    # Crucial: Google Shopping `product_link` is often a Google
                    # page rather than a direct merchant offer. Still investigate
                    # that result using the verified Google product ID.
                    candidate = candidate_from_shopping_row(row, category)
                    if candidate:
                        if candidate.product_id not in candidates or (offer and candidates[candidate.product_id].url == ""):
                            candidates[candidate.product_id] = offer or candidate
                        if not offer:
                            diagnostics["indirect_candidates"] += 1
                        if (category, query) in focused_terms:
                            focused_product_ids.add(candidate.product_id)
            except ScanError:
                warnings.append(f"{category}: bir arama tamamlanamadı")
        outcome[category] = {"successes": succeeded, "total_queries": len(queries), "offers": list(matches.values())}
        if succeeded == 0:
            warnings.append(f"{category}: bu kategorideki sonuçlar güncellenemedi")
    diagnostics["detail_candidates"] = len(candidates)
    checked = checked_product_ids if checked_product_ids is not None else {}
    if max_product_details:
        # Rotation checks products with the oldest last seller comparison first.
        ordered = sorted(candidates.items(), key=lambda pair: (
            # Never investigate already checked results before unseen results.
            bool(checked.get(pair[0], 0)),
            # Rejected Google-only links are the highest-value enrichment.
            bool(pair[1].url),
            0 if pair[0] in focused_product_ids else 1,
            # An eligible PAW sensor mouse gets precedence over generic listings.
            0 if pair[1].category == "mouse" and sensor_is_eligible(pair[1].sensor) else 1,
            pair[1].price, pair[0]))
        for product_id, original in ordered[:max_product_details]:
            try:
                detailed = product_fetcher(key, product_id)
                diagnostics["details_checked"] += 1
                seller_offers = parse_product_stores(detailed, original)
                diagnostics["details_verified_offers"] += len(seller_offers)
                if seller_offers:
                    by_id = {offer.id: offer for offer in outcome[original.category]["offers"]}
                    for offer in seller_offers:
                        if offer.id not in by_id or offer.price < by_id[offer.id].price:
                            by_id[offer.id] = offer
                    outcome[original.category]["offers"] = list(by_id.values())
                checked[product_id] = now
            except ScanError:
                warnings.append("Bazı mağaza fiyatları doğrulanamadı")
    # Diagnostics are useful in the Actions log; public feed stays uncluttered.
    scan_queries.last_diagnostics = diagnostics
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
        # Different models rotate across many queries/days. A successful
        # narrow search must not erase yesterday's findings from other queries.
        # Keep only recently observed offers; old/stale shop prices expire.
        recent_old = [identifier for identifier in active.get(category, [])
                      if identifier in products and now - int(products[identifier].get("last_seen", 0)) <= VISIBLE_OFFER_SECONDS]
        active[category] = list(dict.fromkeys(new_ids + recent_old))
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
    buckets = {}
    products = state.get("products", {})
    for category in CATEGORIES:
        for identifier in state.get("active", {}).get(category, []):
            row = products.get(identifier)
            if not row or row.get("category") != category:
                continue
            # Historical state may contain obsolete/unknown retailers. Exclude
            # them even before the next scheduled scan rewrites the state.
            if not trusted_retailer(row.get("link", "")):
                continue
            price = float(row.get("price") or 0)
            if price <= 0 or price >= 1000000:
                continue
            # Old offers are NOT evidence that the shop still sells at that price.
            if now - int(row.get("last_seen", 0)) > VISIBLE_OFFER_SECONDS:
                continue
            if category == "mouse" and not sensor_is_eligible(row.get("sensor", "")):
                continue
            key = row.get("model_key") or product_model_key(row["title"], category,
                                                              str(row.get("product_id", "")))
            buckets.setdefault((category, key), []).append(row)
    items = []
    for (category, model_key), variants in buckets.items():
        # Keep one least-price offer per seller. Do not claim we surveyed all shops.
        sellers = {}
        for row in variants:
            store_key = trusted_retailer(row.get("link", "")).casefold().strip()
            if not store_key:
                continue
            if store_key not in sellers or float(row["price"]) < float(sellers[store_key]["price"]):
                sellers[store_key] = row
        offers = sorted(sellers.values(), key=lambda x: (float(x["price"]),
                        is_google_comparison_url(x.get("link", "")), x["store"].casefold()))
        if not offers:
            continue
        best = offers[0]
        last_drop = best.get("last_drop")
        price = float(best["price"])
        drop_amount = (round(max(0.0, float(best.get("last_drop_from") or price) - price), 2)
                       if last_drop and now - int(last_drop) <= FRESH_FOR_SECONDS else 0)
        items.append({
            "id": best["id"], "category": category, "title": best["title"],
            "store": trusted_retailer(best.get("link", "")), "price": price,
            "original_price": best.get("original_price"), "link": best.get("link", ""),
            "image": best.get("image", ""), "connectivity": best.get("connectivity", "unknown"),
            "sensor": best.get("sensor", ""),
            "first_seen": min(int(x.get("first_seen", now)) for x in offers),
            "last_seen": int(best["last_seen"]), "lowest_price": best.get("lowest_price", price),
            "is_new": now - min(int(x.get("first_seen", now)) for x in offers) <= FRESH_FOR_SECONDS,
            "drop_amount": drop_amount,
            "price_checked_at": int(best["last_seen"]),
            "offer_count": len(offers),
            "offers": [{"store": trusted_retailer(o.get("link", "")), "price": float(o["price"]),
                        "link": o.get("link", ""), "last_seen": int(o["last_seen"])}
                       for o in offers[:10]],
        })
    items.sort(key=lambda row: (row["price"], row["category"], row["title"].casefold()))
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
        "approved_retailers": [label for _, label in APPROVED_RETAILERS],
    }
    return {"schema": 1, "generated_at": now, "status": status, "products": items}


def run(state_path: Path = STATE_PATH, feed_path: Path = FEED_PATH,
        key: str = "", do_scan: bool = True, now: int | None = None, fetcher=fetch_query,
        *, extra_searches: int = 0, product_fetcher=fetch_product_stores):
    now = int(now if now is not None else time.time())
    state = load_state(state_path)
    key = key.strip()
    if do_scan:
        state["last_attempt"] = now
        if not key:
            state["last_error"] = "Canlı tarama için GitHub Actions API anahtarı henüz eklenmedi."
        else:
            try:
                extra_searches = min(max(0, int(extra_searches)), 3)
                checked = state.setdefault("checked_products", {})
                if not isinstance(checked, dict):
                    checked = state["checked_products"] = {}
                # 4 broad + 0..2 focused discoveries + at most 1 shop lookup.
                # At the free tier, a full nightly run is ~7 calls (217/31 days).
                cursor = int(state.get("discovery_cursor", 0))
                discoveries = choose_discovery_queries(cursor, min(2, extra_searches))
                result, warning, total, completed = scan_queries(
                    key, fetcher, focus_queries=discoveries,
                    product_fetcher=product_fetcher,
                    max_product_details=1 if extra_searches >= 3 else 0,
                    checked_product_ids=checked, now=now)
                if discoveries and completed >= 4:
                    state["discovery_cursor"] = cursor + 1
                if len(checked) > 250:
                    oldest = sorted(checked, key=lambda x: checked[x])[:len(checked)-250]
                    for item in oldest:
                        del checked[item]
                if completed == 0:
                    raise ScanError("Ürün sağlayıcısından veri alınamadı; önceki sonuçlar korundu.")
                merge_scan(state, result, now)
                state["last_error"] = ""
                state["last_warning"] = warning
                state["last_raw_count"] = total
                state["last_completed_queries"] = completed
                state["last_scan_diagnostics"] = getattr(scan_queries, "last_diagnostics", {})
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
    # Account API uses zero search credits. Only enrich when enough spare credits.
    remaining = fetch_remaining_quota(key) if key and not args.no_scan else None
    # The account endpoint can be unavailable even with a healthy API key.
    # Keep 4 general + 2 focused + 1 seller-detail request per scheduled night
    # (<=217 in 31 days) rather than silently turning off seller verification.
    # Manual runs can consume more quota; check SerpApi usage if scans stop.
    extra = min(3, max(0, remaining - MIN_EXTRA_CREDIT_RESERVE - 4)) if remaining is not None else 3
    feed = run(state_path=args.state, feed_path=args.feed, key=key,
               do_scan=not args.no_scan, extra_searches=extra)
    status = feed["status"]
    print(f"Fiyat Avcısı: {len(feed['products'])} uygun ürün; son başarılı tarama: {status['last_success'] or 'yok'}")
    if status["last_error"]:
        print(f"UYARI: {status['last_error']}")
    if status["warning"]:
        print(f"UYARI: {status['warning']}")
    if not args.no_scan:
        saved = read_json(args.state, {})
        diagnostic = saved.get("last_scan_diagnostics", {})
        if diagnostic:
            print("Tarama tanisi (magaza harici urunler halka acik listelenmez): " +
                  ", ".join(f"{key}={value}" for key, value in diagnostic.items()))


if __name__ == "__main__":
    main()
