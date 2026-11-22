import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from amazon_api import CreatorsClient, AmazonAPIError, TOKEN_URL, BASE_URL
from catalog import (normalize_item, detect_category, detect_connection, detect_sensor,
                     detect_keyboard_type, extract_price, is_amazon_link)
from cloud_publish import build_feed, clean_feed, sync, CACHE_SECONDS

NOW = 1795000000

def amazon_item(asin='B0ABC12345', title='James Donkey JDM11 PAW3311 Beyaz Kablosuz Gaming Mouse',
                price=699, currency='TRY', seller='Amazon.com.tr', url=None, details=None):
    return {'asin':asin, 'detailPageURL':url or 'https://www.amazon.com.tr/dp/'+asin+'?tag=verified-21',
            'itemInfo':{'title':{'displayValue':title},'features':{'displayValues':details or []},
                        'byLineInfo':{'brand':{'displayValue':'James Donkey'}}},
            'images':{'primary':{'medium':{'url':'https://m.media-amazon.com/images/I/example.jpg'}}},
            'offersV2':{'listings':[{'condition':{'value':'New'},
                   'availability':{'type':'IN_STOCK'},
                   'price':{'money':{'amount':price,'currency':currency}},
                   'merchantInfo':{'name':seller}}]}}

class TestClassification(unittest.TestCase):
    def test_known_mouse(self):
        p=normalize_item(amazon_item(),NOW)
        self.assertEqual(p['sensor'],'PAW3311')
        self.assertEqual(p['price'],699)
        self.assertEqual(p['connection'],'wireless')
        self.assertEqual(p['color'],'Beyaz')
        self.assertEqual(p['seller_type'],'amazon')
        self.assertIn('verified-21',p['link'])

    def test_keyboard_membrane_mechanical_feel(self):
        p=normalize_item(amazon_item(title='James Donkey JDK99 Mekanik Hisli Membran Kablosuz Klavye'),NOW)
        self.assertEqual(p['keyboard_type'],'membrane')
        self.assertEqual(p['category'],'keyboard')

    def test_hall_keyboard(self):
        p=normalize_item(amazon_item(title='Manyetik Hall Effect Gaming Klavye'),NOW)
        self.assertEqual(p['keyboard_type'],'hall')

    def test_unknown_sensor_not_assumed(self):
        p=normalize_item(amazon_item(title='Siyah Gaming Mouse'),NOW)
        self.assertEqual(p['sensor'],'')

    def test_unknown_connection_not_assumed(self):
        self.assertEqual(detect_connection('Gaming Mouse RGB DPI 12000'),'unknown')

    def test_both_connection(self):
        self.assertEqual(detect_connection('kablolu ve Bluetooth 2.4 GHz'),'both')

    def test_accessories_excluded(self):
        for name in ['Gaming mousepad','Klavye ve Mouse Seti','Mechanical keyboard keycap']:
            self.assertIsNone(detect_category(name),name)

    def test_non_amazon_urls_excluded(self):
        for url in ['http://www.amazon.com.tr/dp/B0ABC12345',
                    'https://amazon.com.tr.evil.com/dp/B0ABC12345',
                    'https://www.amazon.com/dp/B0ABC12345']:
            self.assertFalse(is_amazon_link(url),url)
            self.assertIsNone(normalize_item(amazon_item(url=url),NOW))

    def test_non_try_and_nonsense_price_excluded(self):
        for price,currency in [(400,'USD'),(0,'TRY'),(-1,'TRY'),(1000001,'TRY'),('bad','TRY')]:
            self.assertIsNone(normalize_item(amazon_item(price=price,currency=currency),NOW))

    def test_used_offer_excluded(self):
        row=amazon_item()
        row['offersV2']['listings'][0]['condition']['value']='Used'
        self.assertIsNone(normalize_item(row,NOW))

    def test_marketplace_seller(self):
        p=normalize_item(amazon_item(seller='Mağazam'),NOW)
        self.assertEqual(p['seller_type'],'marketplace')

    def test_only_verified_sensor_pattern(self):
        self.assertEqual(detect_sensor('PAW3311 sensor'),'PAW3311')
        self.assertEqual(detect_sensor('PAW33111'),'')

class TestAPI(unittest.TestCase):
    def test_token_and_requests(self):
        calls=[]
        def fake(url,payload,headers=None):
            calls.append((url,payload,headers))
            if url==TOKEN_URL: return {'access_token':'test-only','expires_in':3600}
            if url.endswith('searchItems'): return {'searchResult':{'items':[amazon_item()]}}
            return {'itemsResult':{'items':[amazon_item()]}}
        api=CreatorsClient('id','secret','tag-21',requester=fake,throttle=0)
        self.assertEqual(len(api.search('gaming mouse')),1)
        self.assertEqual(len(api.get_items(['B0ABC12345'])),1)
        self.assertEqual(sum(x[0]==TOKEN_URL for x in calls),1)
        self.assertTrue(all(x[2].get('x-marketplace')=='www.amazon.com.tr' for x in calls[1:]))
        self.assertEqual(calls[1][1]['partnerTag'],'tag-21')

    def test_search_page_limit(self):
        api=CreatorsClient('id','secret','tag-21')
        with self.assertRaises(ValueError):api.search('mouse',page=11)
        with self.assertRaises(ValueError):api.get_items(['a']*11)

class MockClient:
    def __init__(self):self.queries=[];self.checked=[]
    def search(self,keywords,page=1):
        self.queries.append((keywords,page))
        if page==1:return [amazon_item()]
        return []
    def get_items(self,asins):
        self.checked.extend(asins)
        return [amazon_item(asin=asin) for asin in asins]

class TestSync(unittest.TestCase):
    def test_sync_discovers_then_refreshes_and_keeps_id(self):
        with tempfile.TemporaryDirectory() as d:
            cat,feed=Path(d)/'cat.json',Path(d)/'feed.json'
            client=MockClient()
            x=sync(client=client,now=NOW,catalog_path=cat,feed_path=feed,discover_limit=1,refresh_limit=30)
            self.assertEqual(x['products'][0]['asin'],'B0ABC12345')
            self.assertEqual(json.loads(cat.read_text())['asins']['B0ABC12345']['category'],'mouse')
            sync(client=client,now=NOW+150,catalog_path=cat,feed_path=feed,discover_limit=0,refresh_limit=30)
            self.assertIn('B0ABC12345',client.checked)

    def test_old_serpapi_data_never_imported(self):
        old={'products':[{'asin':'B0ABC12345','price':99,'checked_at':NOW,'source':'serpapi'}]}
        self.assertEqual(clean_feed(old,NOW),[])

    def test_expired_amazon_data_removed(self):
        old={'products':[{'asin':'B0ABC12345','price':99,'checked_at':NOW-CACHE_SECONDS,'source':'amazon-creators-api'}]}
        self.assertEqual(clean_feed(old,NOW),[])

    def test_unconfigured_is_empty_and_honest(self):
        with tempfile.TemporaryDirectory() as d:
            cat,feed=Path(d)/'cat.json',Path(d)/'feed.json'
            with patch.dict('os.environ',{},clear=True):
                result=sync(now=NOW,catalog_path=cat,feed_path=feed)
            self.assertFalse(result['status']['configured'])
            self.assertEqual(result['products'],[])
            self.assertTrue(cat.exists())

    def test_failed_fetch_keeps_recent_but_not_expired(self):
        class Bad:
            def search(self,*a,**k):raise AmazonAPIError('test')
            def get_items(self,*a,**k):raise AmazonAPIError('test')
        with tempfile.TemporaryDirectory() as d:
            cat,feed=Path(d)/'cat.json',Path(d)/'feed.json'
            write={'schema':3,'products':[normalize_item(amazon_item(),NOW-100)],
                   'status':{'last_success':NOW-100}}
            feed.write_text(json.dumps(write))
            result=sync(client=Bad(),now=NOW,catalog_path=cat,feed_path=feed,discover_limit=1)
            self.assertEqual(len(result['products']),1)
            self.assertIn('başarısız',result['status']['last_error'])

    def test_store_only_asin_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            cat,feed=Path(d)/'cat.json',Path(d)/'feed.json'
            sync(client=MockClient(),now=NOW,catalog_path=cat,feed_path=feed,discover_limit=1)
            catalog=json.loads(cat.read_text())
            self.assertNotIn('price',str(catalog))
            self.assertNotIn('title',str(catalog))
            self.assertNotIn('699',str(catalog))

if __name__=='__main__': unittest.main()
