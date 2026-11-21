"""Offline coverage for the GitHub Pages publishing workflow."""
import json
import tempfile
import unittest
from pathlib import Path

from cloud_publish import run, public_feed, empty_state, scan_queries
from scanner import ScanError


class CloudPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state = Path(self.temp_dir.name) / 'state.json'
        self.feed = Path(self.temp_dir.name) / 'feed.json'
        self.now = 1795290000

    def fake_fetcher(self, key, query):
        self.assertEqual(key, 'test-key-do-not-publish')
        if 'klavye' in query and 'kablosuz' in query:
            return [dict(title='Nova Wireless Gaming Klavye', source='Mağaza A',
                         price='1.100,00 TL', link='https://example.com/a', product_id='kb-1'),
                    dict(title='Aşırı Pahalı Kablosuz Gaming Klavye', source='Mağaza B',
                         extracted_price=1100.01, link='https://example.com/expensive',product_id='kb-2')]
        if 'klavye' in query:
            return [dict(title='Vector Kablolu Mekanik Gaming Klavye', source='Mağaza C',
                         extracted_price=750, link='https://example.com/b',product_id='kb-3')]
        if 'kablosuz gaming mouse' in query:
            return [dict(title='Falcon Wireless Gaming Mouse 16000 DPI', source='Mağaza D',
                         extracted_price=999.99, link='https://example.com/c',product_id='mouse-1')]
        return [dict(title='Duo Kablolu Gaming Mouse', source='Mağaza E',
                     extracted_price=1000, link='https://example.com/d',product_id='mouse-2'),
                dict(title='Çok Pahalı Kablolu Gaming Mouse', source='Mağaza F',
                     extracted_price=1001, link='https://example.com/e',product_id='mouse-3')]

    def test_first_run_creates_live_feed_and_applies_limits(self):
        data = run(self.state, self.feed, key='test-key-do-not-publish', now=self.now,
                   fetcher=self.fake_fetcher)
        self.assertEqual(len(data['products']), 4)
        self.assertTrue(data['status']['public_site'])
        self.assertEqual(data['status']['last_success'], self.now)
        self.assertFalse(data['status']['demo'])
        self.assertEqual({p['connectivity'] for p in data['products']}, {'wired', 'wireless'})
        self.assertTrue(all(p['price'] <= (1100 if p['category'] == 'keyboard' else 1000)
                            for p in data['products']))
        self.assertEqual(json.loads(self.feed.read_text())['products'], data['products'])
        self.assertEqual(data['status']['last_error'], '')
        self.assertNotIn('test-key', self.feed.read_text())

    def test_price_drop_history_and_recovery(self):
        run(self.state, self.feed, key='test-key-do-not-publish', now=self.now,
            fetcher=self.fake_fetcher)

        def cheaper(key, query):
            if 'kablosuz gaming mouse' in query:
                return [dict(title='Falcon Wireless Gaming Mouse 16000 DPI', source='Mağaza D',
                             extracted_price=799, link='https://example.com/c', product_id='mouse-1')]
            return self.fake_fetcher(key,query)

        data = run(self.state, self.feed, key='test-key-do-not-publish', now=self.now+3600,
                   fetcher=cheaper)
        mouse = [p for p in data['products'] if p['store']=='Mağaza D'][0]
        self.assertEqual(mouse['drop_amount'], 200.99)
        self.assertFalse(mouse['is_new'] is False)  # Seen less than 48 hours ago
        state = json.loads(self.state.read_text())
        self.assertEqual(len(state['products'][mouse['id']]['history']), 2)
        # A broken provider does not clear last good results.
        def failing(_key, _query):
            raise ScanError('offline')
        failed = run(self.state, self.feed, key='test-key-do-not-publish', now=self.now+7200,
                     fetcher=failing)
        self.assertEqual(failed['status']['last_success'], self.now+3600)
        self.assertEqual(len(failed['products']), 4)
        self.assertTrue(failed['status']['last_error'])

    def test_partial_query_failure_preserves_other_products(self):
        first = run(self.state, self.feed, key='test-key-do-not-publish', now=self.now,
                    fetcher=self.fake_fetcher)
        old_keyboard_ids = {x['id'] for x in first['products'] if x['category'] == 'keyboard'}

        def partial(key, query):
            if query == 'kablolu gaming klavye':
                raise ScanError('connection')
            return self.fake_fetcher(key,query)

        updated = run(self.state, self.feed, key='test-key-do-not-publish', now=self.now+3600,
                      fetcher=partial)
        new_keyboard_ids = {x['id'] for x in updated['products'] if x['category'] == 'keyboard'}
        self.assertEqual(old_keyboard_ids, new_keyboard_ids)
        self.assertTrue(updated['status']['warning'])

    def test_empty_without_api_never_fakes_shopping_results(self):
        data = run(self.state, self.feed, key='', now=self.now)
        self.assertEqual(data['products'], [])
        self.assertFalse(data['status']['configured'])
        self.assertIsNone(data['status']['last_success'])
        self.assertIn('API', data['status']['last_error'])

    def test_stale_feed_warning(self):
        state = empty_state()
        state['last_success'] = self.now - 40*3600
        feed = public_feed(state, True, self.now)
        self.assertTrue(feed['status']['stale'])
        self.assertEqual(feed['products'], [])

    def test_corrupt_state_is_not_overwritten(self):
        self.state.write_text('{bad json', encoding='utf8')
        with self.assertRaises(ValueError):
            run(self.state, self.feed, key='test-key-do-not-publish', now=self.now,
                fetcher=self.fake_fetcher)
        self.assertEqual(self.state.read_text(encoding='utf8'), '{bad json')

    def test_four_queries_per_run(self):
        calls=[]
        def fake(key, query):
            calls.append(query)
            return []
        _, _, _, successful = scan_queries('valid', fake)
        self.assertEqual(successful, 4)
        self.assertEqual(len(calls), 4)


if __name__ == '__main__':
    unittest.main()
