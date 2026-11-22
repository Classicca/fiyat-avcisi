"""Strict Amazon-only product normalization; never guess missing attributes."""
from __future__ import annotations
import re
from urllib.parse import urlparse

SENSORS = ('PAW3311', 'PAW3315', 'PAW3333', 'PAW3335', 'PAW3370', 'PAW3395',
           'PAW3399', 'PAW3950', 'PAW3955', 'PMW3360', 'PMW3366', 'PMW3389',
           'HERO', 'HERO 2', 'FOCUS PRO', 'FOCUS PRO 30K', 'FOCUS PRO 35K')
# Curated selectable high-tier family; not a claim that all numeric model numbers are ordered.
SENSOR_GROUP = {'PAW3311', 'PAW3315', 'PAW3333', 'PAW3335', 'PAW3370', 'PAW3395',
                'PAW3399', 'PAW3950', 'PAW3955', 'PMW3360', 'PMW3366', 'PMW3389',
                'HERO', 'HERO 2', 'FOCUS PRO', 'FOCUS PRO 30K', 'FOCUS PRO 35K'}
COLORS = {'beyaz': 'Beyaz', 'white': 'Beyaz', 'siyah': 'Siyah', 'black': 'Siyah',
          'pembe': 'Pembe', 'pink': 'Pembe', 'gri': 'Gri', 'gray': 'Gri', 'grey': 'Gri',
          'mavi': 'Mavi', 'blue': 'Mavi', 'kırmızı': 'Kırmızı', 'red': 'Kırmızı'}
BANNED = ('mousepad', 'mouse pad', 'fare pedi', 'bilek desteği', 'klavye kılıf',
          'tuş seti', 'keycap', 'switch seti', 'klavye çantası', 'sticker', 'klavye standı',
          'usb alıcı', 'dongle', 'klavye mouse set', 'klavye ve mouse set', 'klavye fare set')


def extract_features(item):
    info = item.get('itemInfo') or {}
    title = ((info.get('title') or {}).get('displayValue') or '').strip()
    features = (info.get('features') or {}).get('displayValues') or []
    brand = (info.get('byLineInfo') or {}).get('brand', {}).get('displayValue') or ''
    return title, '\n'.join([title] + [str(x) for x in features[:12]]), brand.strip()


def normalize_text(value):
    return str(value or '').casefold().replace('ı', 'i')


def detect_category(title):
    text = normalize_text(title)
    if any(term in text for term in BANNED):
        return None
    if any(term in text for term in ('mouse', 'fare ', 'oyuncu faresi')):
        if any(term in text for term in ('klavye', 'keyboard', 'keycap')):
            return None
        return 'mouse'
    if any(term in text for term in ('klavye', 'keyboard')):
        return 'keyboard'
    return None


def detect_connection(info):
    info = normalize_text(info)
    wireless = bool(re.search(r'kablosuz|wireless|bluetooth|2[.,]4\s*ghz|2\.4g\b', info))
    wired = bool(re.search(r'\bkablolu\b|\bwired\b|usb[- ]?c\s*kablo', info))
    if wireless and wired: return 'both'
    if wireless: return 'wireless'
    if wired: return 'wired'
    return 'unknown'


def detect_sensor(info):
    text = str(info or '').upper()
    for sensor in sorted(SENSORS, key=len, reverse=True):
        if re.search(r'(?<![A-Z0-9])' + re.escape(sensor) + r'(?![A-Z0-9])', text):
            return sensor
    return ''


def detect_color(title):
    text = normalize_text(title)
    for word, label in COLORS.items():
        if re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text):
            return label
    return 'Bilinmiyor'


def detect_keyboard_type(info):
    text = normalize_text(info)
    if any(x in text for x in ('hall effect', 'hall-effect', 'manyetik switch', 'magnetic switch')):
        return 'hall'
    if any(x in text for x in ('membran', 'membrane', 'mekanik hisli', 'mechanical feel')):
        return 'membrane'
    if 'mekanik' in text or 'mechanical' in text or 'red switch' in text or 'brown switch' in text:
        return 'mechanical'
    return 'unknown'


def is_amazon_link(url):
    try:
        p = urlparse(url)
        return p.scheme == 'https' and p.hostname in ('amazon.com.tr', 'www.amazon.com.tr')
    except (TypeError, ValueError):
        return False


def extract_price(item):
    listings = ((item.get('offersV2') or {}).get('listings') or [])
    eligible = []
    for offer in listings:
        condition = normalize_text(((offer.get('condition') or {}).get('value')))
        if condition and condition not in ('new', 'yeni'):
            continue
        availability = (offer.get('availability') or {}).get('type', '')
        if availability and str(availability).upper() in ('OUT_OF_STOCK', 'UNAVAILABLE'):
            continue
        money = (((offer.get('price') or {}).get('money')) or {})
        if money.get('currency') != 'TRY':
            continue
        try: price = float(money.get('amount'))
        except (ValueError, TypeError): continue
        if not (1 <= price <= 1_000_000):
            continue
        seller = ((offer.get('merchantInfo') or {}).get('name') or 'Satıcı bilinmiyor').strip()
        is_amazon_seller = seller.casefold() in {'amazon', 'amazon.com.tr', 'amazon.com', 'amazon eu s.a.r.l.', 'amazon eu sarl'}
        eligible.append((price, seller, is_amazon_seller))
    return min(eligible, key=lambda x: x[0]) if eligible else None


def normalize_item(item, now):
    asin = str(item.get('asin') or '').upper().strip()
    if not re.fullmatch(r'[A-Z0-9]{10}', asin):
        return None
    url = item.get('detailPageURL') or ''
    if not is_amazon_link(url):
        return None
    title, info, brand = extract_features(item)
    category = detect_category(title)
    if not category:
        return None
    best = extract_price(item)
    if not best:
        return None
    image = (((item.get('images') or {}).get('primary') or {}).get('medium') or {}).get('url') or ''
    if image and not (image.startswith('https://m.media-amazon.com/') or image.startswith('https://images-eu.ssl-images-amazon.com/') or image.startswith('https://images-na.ssl-images-amazon.com/')):
        image = ''
    price, seller, is_amazon_seller = best
    return {'asin': asin, 'id': asin, 'title': title[:220], 'category': category,
            'price': round(price, 2), 'currency': 'TRY', 'link': url, 'image': image,
            'brand': brand[:60], 'color': detect_color(title), 'connection': detect_connection(info),
            'keyboard_type': detect_keyboard_type(info) if category == 'keyboard' else 'unknown',
            'sensor': detect_sensor(info) if category == 'mouse' else '',
            'seller': seller[:90], 'seller_type': 'amazon' if is_amazon_seller else 'marketplace',
            'checked_at': int(now), 'source': 'amazon-creators-api'}
