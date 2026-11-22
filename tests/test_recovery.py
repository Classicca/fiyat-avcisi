"""The regression that made the allowlist collapse 31 offers to a single card."""
import tempfile
import unittest
from pathlib import Path

from scanner import (parse_offer, candidate_from_shopping_row,
                     model_sensor_from_verified_catalog)
from cloud_publish import run, load_state

class RecoveryTests(unittest.TestCase):
    NOW = 1795290000
    JDM = 'James Donkey JDM11 Beyaz Triple Mode Gaming Mouse'
    JDK = 'James Donkey JDK99 Kablosuz Gaming Klavye'

    def test_google_only_link_never_publishes_without_verified_seller(self):
        row = dict(title=self.JDM, source='İncehesap', extracted_price=699,
                   product_id='1234567890123456',
                   product_link='https://www.google.com/shopping/product/123',
                   thumbnail='https://example.com/mouse.png')
        self.assertIsNone(parse_offer(row, category='mouse'))
        candidate = candidate_from_shopping_row(row, 'mouse')
        self.assertEqual(candidate.sensor, 'PAW3311')
        self.assertEqual(candidate.url, '')
        self.assertEqual(model_sensor_from_verified_catalog('Random Generic Mouse'), '')

    def test_detail_recovers_google_link_mouse_with_verified_direct_offer(self):
        with tempfile.TemporaryDirectory() as d:
            state, feed = Path(d)/'state.json', Path(d)/'feed.json'
            def search(_key, query):
                if 'JDM11' not in query:
                    return []
                return [dict(title=self.JDM, source='İncehesap',
                    extracted_price=699, product_id='1234567890123456',
                    product_link='https://www.google.com/shopping/product/123',
                    thumbnail='https://example.com/mouse.png')]
            def detail(_key, product_id):
                self.assertEqual(product_id, '1234567890123456')
                return {'product_results': {'stores': [
                    {'name':'İncehesap', 'title':'James Donkey JDM11 Beyaz Mouse',
                     'price':'699,00 TL', 'extracted_price':699,
                     'link':'https://www.incehesap.com/james-donkey-jdm11/'},
                    {'name':'Other', 'title':'James Donkey JDM11 Beyaz Mouse',
                     'price':'450,00 TL', 'link':'https://unapproved.example/jdm11'}]}}
            result = run(state, feed, 'fake-key', now=self.NOW, fetcher=search,
                         extra_searches=3, product_fetcher=detail)
            self.assertEqual(len(result['products']),1)
            self.assertEqual(result['products'][0]['store'],'İncehesap')
            self.assertEqual(result['products'][0]['price'],699)
            self.assertEqual(result['products'][0]['sensor'],'PAW3311')
            self.assertEqual(load_state(state)['last_scan_diagnostics']['indirect_candidates'], 1)
            self.assertEqual(load_state(state)['last_scan_diagnostics']['details_verified_offers'], 1)

    def test_no_public_offer_if_only_unapproved_stores(self):
        with tempfile.TemporaryDirectory() as d:
            state, feed = Path(d)/'state.json', Path(d)/'feed.json'
            def search(_key, query):
                if 'JDK99' not in query:
                    return []
                return [dict(title=self.JDK, source='Unverified Source',
                     extracted_price=699, product_id='1234567890123457',
                     product_link='https://www.google.com/shopping/product/123')]
            def detail(_key, product_id):
                return {'product_results': {'stores': [
                    {'name':'Other', 'title':self.JDK,'price':'499 TL',
                     'link':'https://fake-store.example/jdk99'}]}}
            out = run(state, feed, 'fake-key', now=self.NOW,
                      fetcher=search, extra_searches=3, product_fetcher=detail)
            self.assertEqual(out['products'],[])

if __name__ == '__main__':
    unittest.main()
