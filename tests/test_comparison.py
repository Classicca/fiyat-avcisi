"""Unit tests for model+store price comparison; no external paid calls."""
import tempfile
import unittest
from pathlib import Path
from scanner import (parse_offer, parse_product_stores, sensor_is_eligible,
                     product_model_key, is_google_comparison_url)
from cloud_publish import run

JDK99 = 'James Donkey JDK99 Kablosuz RGB Mekanik Hisli Membran Türkçe Q Gaming Klavye'

class PriceComparisonTests(unittest.TestCase):
    def test_sensor_threshold_is_not_numeric_comparison(self):
        for sensor in ('PAW3311','PAW3335','PAW3370','PAW3395','PMW3389'):
            self.assertTrue(sensor_is_eligible(sensor))
        for sensor in ('PAW3327','PMW3325','PAW3310','HERO 25K','', 'PWN3395'):
            self.assertFalse(sensor_is_eligible(sensor))
        sample = dict(title='MageGee Scout Wireless Gaming Mouse PAW3327',
                      source='Pazar', price='799 TL', link='https://www.trendyol.com/m')
        self.assertIsNone(parse_offer(sample, category='mouse'))
        sample['title']='MageGee Scout Wireless Gaming Mouse PAW3311'
        self.assertIsNotNone(parse_offer(sample, category='mouse'))
        sample['title']='Gaming Mouse 26K DPI'
        self.assertIsNone(parse_offer(sample, category='mouse'))

    def test_different_models_not_merged(self):
        self.assertEqual(product_model_key('James Donkey JDK99 RGB Gaming Klavye','keyboard'),
                         product_model_key('James Donkey JDK99 Kablosuz Gaming Klavye','keyboard'))
        self.assertNotEqual(product_model_key('James Donkey JDK99 Gaming Klavye','keyboard'),
                            product_model_key('James Donkey JDK87 Gaming Klavye','keyboard'))
        self.assertNotEqual(product_model_key('James Donkey JDK99 Gaming Klavye','keyboard'),
                            product_model_key('Logitech JDK99 Gaming Klavye','keyboard'))

    def test_google_product_seller_results(self):
        parent = parse_offer({'title': JDK99,'source':'Mağaza A','extracted_price':990,
                              'product_id':'1234567890123456789','link':'https://www.trendyol.com/p'},
                             category='keyboard')
        data = {'product_results':{'stores':[
            {'name':'İncehesap', 'title':JDK99,'extracted_price':809,
             'link':'https://www.incehesap.com/james-donkey-jdk99-klavye/'},
            {'name':'Diğer', 'title':JDK99,'price':'999,00 TL', 'link':'https://www.hepsiburada.com/p'},
            {'name':'Yanlış Model', 'title':JDK99.replace('JDK99','JDK87'),
             'price':'499 TL','link':'https://www.n11.com/p'},
            {'name':'İkinci el', 'title':JDK99,'condition':'Used','price':'250 TL',
             'link':'https://www.idefix.com/p'},
        ]}}
        merchants = parse_product_stores(data, parent)
        self.assertEqual([offer.price for offer in merchants],[809,999])
        self.assertTrue(all(offer.model_key==parent.model_key for offer in merchants))
        self.assertTrue(is_google_comparison_url('https://www.google.com/shopping/product/1'))

    def test_end_to_end_lowest_price_with_store_choices(self):
        with tempfile.TemporaryDirectory() as d:
            state, feed = Path(d)/'state.json', Path(d)/'feed.json'
            google_id = '1234567890123456789'
            def fetch(_key, query):
                if 'JDK99' in query:
                    return [{'title':JDK99,'source':'Mağaza A','extracted_price':990,
                             'product_id':google_id,'link':'https://www.trendyol.com/p'}]
                return []
            def detail(_key, pid):
                self.assertEqual(pid,google_id)
                return {'product_results': {'stores':[
                    {'name':'İncehesap','title':JDK99,'extracted_price':809,
                     'link':'https://www.incehesap.com/jdk99/'},
                    {'name':'Mağaza A','title':JDK99,'extracted_price':990,
                     'link':'https://www.trendyol.com/p'}]}}
            result = run(state,feed,'key',now=1795290000,fetcher=fetch,
                         extra_searches=3,product_fetcher=detail)
            self.assertEqual(len(result['products']),1)
            best=result['products'][0]
            self.assertEqual(best['price'],809)
            self.assertEqual(best['store'],'İncehesap')
            self.assertEqual(best['offer_count'],2)
            self.assertEqual([o['price'] for o in best['offers']],[809,990])
            self.assertTrue(best['link'].startswith('https://www.incehesap.com'))
            self.assertNotIn('key-do-not-publish',feed.read_text())

    def test_unknown_sensors_not_published_from_legacy_history(self):
        with tempfile.TemporaryDirectory() as d:
            from cloud_publish import public_feed, empty_state
            state=empty_state()
            state['products']['a']={'id':'a','category':'mouse','title':'Cheap Gaming Mouse PAW3327',
              'store':'Old Store','price':500,'link':'https://www.pazarama.com','image':'',
              'first_seen':1,'last_seen':1,'sensor':'PAW3327','connectivity':'wired'}
            state['active']['mouse']=['a']
            self.assertEqual(public_feed(state,True,200)['products'],[])

if __name__=='__main__': unittest.main()
