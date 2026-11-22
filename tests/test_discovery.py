"""Catch the JDM11 omission, duplicate-discovery and age/credit regressions."""
import tempfile
import unittest
import json
from pathlib import Path

from discovery import DISCOVERY_QUERIES, choose_discovery_queries
from scanner import parse_offer, product_model_key
from cloud_publish import run, public_feed, load_state, empty_state, VISIBLE_OFFER_SECONDS


class DiscoveryTests(unittest.TestCase):
    NOW = 1795290000
    JDM11 = 'James Donkey JDM11 PAW3311 12.000DPI Triple Mode (Kablolu/Bluetooth/2.4G) Beyaz Gaming Mouse'
    JDK99 = 'James Donkey JDK99 Kablosuz RGB Mekanik Hisli Membran Turkce Q Gaming Klavye'

    def test_first_automatic_discovery_covers_reported_missing_products(self):
        plan = choose_discovery_queries(0, 2)
        self.assertEqual(len(plan), 2)
        self.assertIn(('mouse', DISCOVERY_QUERIES['mouse'][0]), plan)
        self.assertIn(('keyboard', DISCOVERY_QUERIES['keyboard'][0]), plan)
        self.assertTrue(any('JDM11' in query for _, query in plan))
        self.assertTrue(any('JDK99' in query for _, query in plan))

    def test_rotating_discovery_alternates_and_covers_multiple_models(self):
        models = {kind: set() for kind in DISCOVERY_QUERIES}
        for i in range(20):
            plan = choose_discovery_queries(i, 2)
            self.assertEqual({kind for kind, _ in plan}, {'keyboard', 'mouse'})
            for kind, query in plan:
                models[kind].add(query)
        self.assertGreaterEqual(len(models['mouse']), 12)
        self.assertGreaterEqual(len(models['keyboard']), 12)
        self.assertEqual(choose_discovery_queries(0, 1)[0][0], 'mouse')
        self.assertEqual(choose_discovery_queries(1, 1)[0][0], 'keyboard')
        self.assertEqual(choose_discovery_queries(0, 0), ())

    def test_missing_jdm11_is_found_and_kept_across_generic_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp)/'state.json'
            feed_path = Path(tmp)/'feed.json'
            queries = []
            def fetch(_key, q):
                queries.append(q)
                if 'JDM11' in q:
                    return [dict(title=self.JDM11, source='incehesap.com', extracted_price=699,
                                 link='https://www.incehesap.com/james-donkey-jdm11-paw3311-beyaz/',
                                 thumbnail='https://shop.test/jdm11.png')]
                if 'JDK99' in q:
                    return [dict(title=self.JDK99, source='incehesap.com', extracted_price=809,
                                 link='https://www.incehesap.com/james-donkey-jdk99/')]
                return []
            first = run(state_path, feed_path, 'test-key', now=self.NOW, fetcher=fetch, extra_searches=2)
            self.assertEqual(len(queries), 6)  # four broad + two model queries
            self.assertEqual({r['category'] for r in first['products']}, {'keyboard','mouse'})
            mice = [p for p in first['products'] if p['category'] == 'mouse']
            self.assertEqual(mice[0]['price'], 699)
            self.assertEqual(mice[0]['sensor'], 'PAW3311')
            self.assertEqual(mice[0]['connectivity'], 'both')
            self.assertEqual(load_state(state_path)['discovery_cursor'], 1)
            later = run(state_path, feed_path, 'test-key', now=self.NOW+86400,
                        fetcher=lambda _key, _q: [], extra_searches=2)
            self.assertEqual(len(later['products']), 2)  # not erased by rotating search
            # after expiry, old observations must not be presented as valid deals
            expired = run(state_path, feed_path, 'test-key',
                          now=self.NOW+VISIBLE_OFFER_SECONDS+1,
                          fetcher=lambda _key, _q: [], extra_searches=0)
            self.assertEqual(expired['products'], [])

    def test_id_groups_same_model_across_shops(self):
        one = parse_offer({'title': self.JDM11, 'source': 'Shop A', 'price': 899,
                          'link':'https://shop-a.example/jdm11'}, category='mouse')
        two = parse_offer({'title': self.JDM11.replace('Beyaz', 'Siyah'), 'source': 'Shop B', 'price':699,
                          'link':'https://shop-b.example/jdm11'}, category='mouse')
        self.assertIsNotNone(one)
        self.assertEqual(one.model_key, two.model_key)
        self.assertNotEqual(one.id, two.id)

if __name__ == '__main__': unittest.main()
