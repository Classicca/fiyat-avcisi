"""Official Amazon Creators API connector. No HTML scraping or SerpApi.

Docs: https://affiliate-program.amazon.com/creatorsapi/docs/en-us/get-started/using-curl
Requires approved TR Creators credentials and an Amazon.com.tr partner tag.
"""
from __future__ import annotations
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TOKEN_URL = 'https://api.amazon.co.uk/auth/o2/token'  # Turkey uses EU LwA 3.2.
BASE_URL = 'https://creatorsapi.amazon/catalog/v1'
MARKETPLACE = 'www.amazon.com.tr'
RESOURCES = ['images.primary.medium', 'itemInfo.title', 'itemInfo.features',
             'itemInfo.byLineInfo', 'offersV2.listings.price',
             'offersV2.listings.availability', 'offersV2.listings.merchantInfo',
             'offersV2.listings.condition', 'offersV2.listings.isBuyBoxWinner']

class AmazonAPIError(Exception):
    pass


def http_json(url, payload, headers=None, timeout=25):
    request = Request(url, json.dumps(payload).encode('utf-8'),
                      headers={'Content-Type': 'application/json', 'User-Agent': 'FiyatAvcisi/3.0', **(headers or {})},
                      method='POST')
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        # No response bodies in logs: upstream errors might reveal sensitive info.
        raise AmazonAPIError(f'Amazon API HTTP {exc.code}. Erişim/kota/kimlik bilgilerini kontrol et.') from exc
    except (URLError, TimeoutError, ValueError) as exc:
        raise AmazonAPIError(f'Amazon API bağlantı/yanıt hatası: {type(exc).__name__}.') from exc


class CreatorsClient:
    def __init__(self, client_id, client_secret, partner_tag, requester=http_json, throttle=1.05):
        if not all([client_id, client_secret, partner_tag]):
            raise AmazonAPIError('Creators API kimlik bilgileri eksik.')
        self.client_id = client_id
        self.client_secret = client_secret
        self.partner_tag = partner_tag
        self.requester = requester
        self.throttle = throttle
        self.token = ''
        self.token_until = 0
        self.last_call = 0

    def _token(self):
        if self.token and time.time() < self.token_until:
            return self.token
        payload = {'grant_type': 'client_credentials', 'client_id': self.client_id,
                   'client_secret': self.client_secret, 'scope': 'creatorsapi::default'}
        result = self.requester(TOKEN_URL, payload)
        self.token = result.get('access_token') or ''
        if not self.token:
            raise AmazonAPIError('Amazon erişim tokenı üretilemedi.')
        self.token_until = time.time() + max(60, int(result.get('expires_in', 3600)) - 90)
        return self.token

    def _request(self, endpoint, payload):
        token = self._token()
        delta = time.monotonic() - self.last_call
        if self.last_call and delta < self.throttle:
            time.sleep(self.throttle - delta)
        headers = {'Authorization': 'Bearer ' + token, 'x-marketplace': MARKETPLACE}
        self.last_call = time.monotonic()
        result = self.requester(BASE_URL + endpoint, {'marketplace': MARKETPLACE,
                                   'partnerTag': self.partner_tag, **payload}, headers)
        if not isinstance(result, dict) or result.get('errors'):
            raise AmazonAPIError('Amazon Creators API ürün isteği başarısız oldu.')
        return result

    def search(self, keywords, page=1):
        if page < 1 or page > 10:
            raise ValueError('API arama sayfası 1-10 aralığında olmalı.')
        result = self._request('/searchItems', {
            'keywords': keywords, 'itemCount': 10, 'itemPage': page,
            'searchIndex': 'All', 'resources': RESOURCES,
        })
        return result.get('searchResult', {}).get('items', []) or []

    def get_items(self, asins):
        if not (1 <= len(asins) <= 10):
            raise ValueError('GetItems için 1-10 ASIN gerekli.')
        result = self._request('/getItems', {'itemIds': asins, 'itemIdType': 'ASIN', 'resources': RESOURCES})
        return result.get('itemsResult', {}).get('items', []) or []
