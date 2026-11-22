"""Amazon-only catalog sync and static feed generation for GitHub Pages.

No SerpApi or scraping; credentials are read exclusively from environment.
No Amazon-derived price/title/image is kept beyond 24h (public feed is refreshed
and old records purged). Durable catalog only stores ASINs and scan cursors.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from amazon_api import CreatorsClient, AmazonAPIError
from catalog import normalize_item

ROOT = Path(__file__).resolve().parent
CATALOG_FILE = ROOT / 'data' / 'amazon_catalog.json'
FEED_FILE = ROOT / 'data' / 'feed.json'
CACHE_SECONDS = 23 * 3600  # below Amazon's 24-hour cache ceiling
MAX_CATALOG = 1500
MAX_REFRESH = 160   # refetch up to 160 previously discovered ASINs per scheduled cycle
SEARCHES_PER_RUN = 8
PAGES_PER_SEARCH = 2

# Different queries are rotated; the API does not provide an exhaustive catalog dump.
QUERIES = [
 'oyuncu mouse', 'gaming mouse', 'kablosuz oyuncu mouse', 'kablolu oyuncu mouse',
 'PixArt PAW3311 mouse', 'PAW3395 mouse', 'beyaz gaming mouse', 'ergonomik oyuncu mouse',
 'Logitech gaming mouse', 'Razer gaming mouse', 'SteelSeries gaming mouse',
 'James Donkey mouse', 'Rampage gaming mouse', 'GamePower mouse',
 'mechanical keyboard', 'mekanik gaming klavye', 'oyuncu klavyesi', 'kablosuz gaming klavye',
 'kablolu mekanik klavye', 'membran gaming klavye', 'hall effect klavye',
 'white gaming keyboard', 'beyaz mekanik klavye', 'red switch mekanik klavye',
 'Logitech klavye', 'Razer gaming klavye', 'Rampage klavye', 'James Donkey klavye',
 'GamePower klavye', 'Royal Kludge klavye', 'Ajazz klavye', 'Redragon klavye',
]


def load_json(path, fallback):
    try:
        x = json.loads(Path(path).read_text('utf-8'))
        return x if isinstance(x, dict) else fallback
    except (OSError, ValueError):
        return fallback


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n', 'utf-8')
    tmp.replace(path)


def clean_feed(existing, now):
    # Never import legacy Google Shopping/SerpApi content into the Amazon-only site.
    products = []
    for row in existing.get('products', []):
        if not isinstance(row, dict) or row.get('source') != 'amazon-creators-api':
            continue
        checked = int(row.get('checked_at') or 0)
        if checked <= now and now - checked < CACHE_SECONDS:
            products.append(row)
    return products


def build_feed(products, *, now, configured, last_success, last_attempt, last_error='', warning=''):
    products = sorted(products, key=lambda r: (r['price'], r['title'].casefold()))
    return {
        'schema': 3, 'generated_at': now,
        'status': {'source': 'Amazon Türkiye · Creators API', 'configured': bool(configured),
                   'last_success': last_success, 'last_attempt': last_attempt,
                   'last_error': last_error, 'warning': warning,
                   'products': len(products), 'demo': False,
                   'disclaimer': 'Amazon fiyatları değişebilir; son fiyat Amazon ürün sayfasında geçerlidir.'},
        'products': products,
    }


def sync(client=None, *, now=None, catalog_path=CATALOG_FILE, feed_path=FEED_FILE,
         discover_limit=SEARCHES_PER_RUN, refresh_limit=MAX_REFRESH):
    now = int(now or time.time())
    catalog = load_json(catalog_path, {'schema': 3, 'asins': {}, 'query_cursor': 0, 'refresh_cursor': 0})
    if catalog.get('schema') != 3 or not isinstance(catalog.get('asins'), dict):
        raise ValueError('Amazon katalog dosyası beklenen biçimde değil; üzerine yazılmadı.')
    prior_feed = load_json(feed_path, {'products': [], 'status': {}})
    previous = {item['asin']: item for item in clean_feed(prior_feed, now) if 'asin' in item}
    configured = bool(client)
    creds_ready = all([os.environ.get('AMAZON_CREATORS_CLIENT_ID'), os.environ.get('AMAZON_CREATORS_CLIENT_SECRET'), os.environ.get('AMAZON_ASSOCIATE_TAG')])
    configured = configured or creds_ready
    error, warning = '', ''
    scan_ok, api_calls, seen = False, 0, 0
    last_success = prior_feed.get('status', {}).get('last_success')
    if not configured:
        error = 'Amazon Creators API anahtarları GitHub Secrets bölümüne henüz eklenmedi.'
    else:
        try:
            if client is None:
                client = CreatorsClient(os.environ['AMAZON_CREATORS_CLIENT_ID'],
                                        os.environ['AMAZON_CREATORS_CLIENT_SECRET'],
                                        os.environ['AMAZON_ASSOCIATE_TAG'])
            # Fetch known identifiers first: keeps a broad catalog useful.
            known = list(catalog['asins'])
            if known and refresh_limit > 0:
                cursor = int(catalog.get('refresh_cursor', 0)) % len(known)
                refresh = (known[cursor:] + known[:cursor])[:refresh_limit]
                for i in range(0, len(refresh), 10):
                    rows = client.get_items(refresh[i:i+10]); api_calls += 1
                    for row in rows:
                        product = normalize_item(row, now)
                        if product:
                            previous[product['asin']] = product; seen += 1
                catalog['refresh_cursor'] = (cursor + len(refresh)) % len(known)
            # Rotate searches and fetch 1-2 pages from each. No all-results promise.
            qstart = int(catalog.get('query_cursor', 0)) % len(QUERIES)
            count = min(max(0, discover_limit), len(QUERIES))
            for i in range(count):
                query = QUERIES[(qstart + i) % len(QUERIES)]
                for page in range(1, PAGES_PER_SEARCH + 1):
                    rows = client.search(query, page=page); api_calls += 1
                    for row in rows:
                        product = normalize_item(row, now)
                        if product:
                            previous[product['asin']] = product; seen += 1
                            if len(catalog['asins']) < MAX_CATALOG or product['asin'] in catalog['asins']:
                                catalog['asins'][product['asin']] = {'category': product['category']}
                    if len(rows) < 10:
                        break
            catalog['query_cursor'] = (qstart + count) % len(QUERIES)
            scan_ok = True
            last_success = now
            if not seen:
                warning = 'API yanıt verdi ancak geçerli TRY fiyatlı klavye/mouse bulunamadı.'
        except (AmazonAPIError, KeyError, ValueError) as exc:
            error = f'Son API kontrolü başarısız: {exc}'
    # Publishing previous fresh records remains safe during a transient failure.
    fresh = [p for p in previous.values() if now - int(p['checked_at']) < CACHE_SECONDS]
    status = build_feed(fresh, now=now, configured=configured, last_success=last_success,
                        last_attempt=now, last_error=error, warning=warning)
    write_json(feed_path, status)
    # Only persist durable IDs/cursors after successful API operations.
    if scan_ok or not Path(catalog_path).exists():
        write_json(catalog_path, catalog)
    print(f'Amazon Creators: configured={configured} ok={scan_ok} calls={api_calls} '
          f'matched={seen} live={len(fresh)} catalog_asins={len(catalog["asins"])} '
          f'error={bool(error)}')
    return status


if __name__ == '__main__':
    sync()
