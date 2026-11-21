import unittest
from scanner import parse_price, is_keyboard, is_mouse, parse_offer, collect_offers, ScanError, SEARCH_QUERIES, detect_connectivity

class ScannerTests(unittest.TestCase):
    def test_price_tr(self):
        self.assertEqual(parse_price('1.099,90 TL'), 1099.9)
        self.assertEqual(parse_price('₺1.099'), 1099)
        self.assertEqual(parse_price('1,099.90 TRY'), 1099.9)
        self.assertEqual(parse_price('999 TL'), 999)
        self.assertIsNone(parse_price('Fiyat yok'))
        self.assertIsNone(parse_price(0))

    def test_keyboard_filter(self):
        self.assertTrue(is_keyboard('2.4GHz Kablosuz Gaming Mekanik Klavye'))
        self.assertTrue(is_keyboard('Wireless RGB Gaming Keyboard'))
        self.assertTrue(is_keyboard('Bluetooth mekanik klavye'))
        self.assertTrue(is_keyboard('Kablolu Gaming Klavye'))
        self.assertFalse(is_keyboard('Kablosuz Gaming Klavye Keycap Seti'))
        self.assertFalse(is_keyboard('Wireless Gaming Keyboard Mouse Combo'))
        self.assertFalse(is_keyboard('Kablosuz Klavye ofis'))

    def test_parse_offer(self):
        offer = parse_offer(dict(title='Kablosuz RGB Gaming Klavye', source='Örnek',
                                 extracted_price=1099.95, product_link='https://example.com/p',
                                 product_id='abc', thumbnail='https://example.com/img.png'))
        self.assertIsNotNone(offer)
        self.assertEqual(offer.price, 1099.95)
        self.assertEqual(offer.connectivity, 'wireless')
        self.assertEqual(parse_offer(dict(title='Gaming Klavye', extracted_price=999, product_link='https://example.com')).connectivity, 'unknown')
        self.assertIsNone(parse_offer(dict(title='Wireless RGB Gaming Keyboard', price='$5.99', product_link='https://example.com')))
        self.assertIsNone(parse_offer(dict(title='Wireless RGB Gaming Keyboard', price='999 TL', product_link='javascript:alert(1)')))

    def test_mouse_filter(self):
        self.assertTrue(is_mouse('Logitech G102 Lightsync Gaming Mouse 8000 DPI'))
        self.assertTrue(is_mouse('Razer DeathAdder Essential Oyuncu Fare Kablolu'))
        self.assertTrue(is_mouse('RGB Wireless Gaming Mouse 2.4GHz'))
        self.assertFalse(is_mouse('Kablosuz Ofis Mouse'))
        self.assertFalse(is_mouse('Gaming Mouse Pad XL'))
        self.assertFalse(is_mouse('Gaming Mousepad RGB'))
        self.assertFalse(is_mouse('Gaming Mouse Skates Aksesuar'))
        self.assertFalse(is_mouse('Gaming Mouse ve Klavye Seti'))

    def test_mouse_parser_and_search_categories(self):
        mouse = dict(title='Kablolu Oyuncu Gaming Mouse 16000 DPI', source='Mağaza',
                     extracted_price=1000, product_link='https://example.com/mouse')
        item = parse_offer(mouse, category='mouse')
        self.assertIsNotNone(item)
        self.assertEqual(item.category, 'mouse')
        self.assertEqual(item.connectivity, 'wired')
        self.assertIsNone(parse_offer(mouse, category='keyboard'))
        self.assertIsNone(parse_offer(dict(mouse, title='Gaming Mouse Pad'), category='mouse'))
        self.assertEqual(len(SEARCH_QUERIES), 4)
        def fetch(key, query):
            if 'mouse' in query:
                return [mouse]
            return [dict(title='Wireless RGB Gaming Klavye', source='Mağaza',
                         extracted_price=1099, product_link='https://example.com/keyboard')]
        offers, total, warning = collect_offers('mock', fetcher=fetch)
        self.assertEqual({o.category for o in offers}, {'keyboard', 'mouse'})
        self.assertEqual((total, warning), (4, ''))

    def test_connection_classification(self):
        samples = {
            'Kablolu RGB Gaming Klavye': 'wired',
            'USB kablosuz oyuncu mouse': 'wireless',
            'Bluetooth mekanik klavye': 'wireless',
            'Wired Wireless RGB Gaming Keyboard': 'both',
            '2.4GHz Gaming Mouse': 'wireless',
            'USB Gaming Mouse': 'unknown',
            'Logitech RGB Gaming Mouse': 'unknown',
            'Kablolu ve Kablosuz Gaming Mouse': 'both',
        }
        for title, expected in samples.items():
            with self.subTest(title=title):
                self.assertEqual(detect_connectivity(title), expected)
        self.assertIn(('keyboard', 'kablolu gaming klavye'), SEARCH_QUERIES)
        self.assertIn(('mouse', 'kablosuz gaming mouse'), SEARCH_QUERIES)

    def test_dedup_and_errors(self):
        sample = dict(title='Kablosuz RGB Gaming Klavye', source='Mağaza', extracted_price=999, product_link='https://example.com', product_id='xy')
        def mock(key, q):
            return [sample] if q == 'first' else [dict(sample, extracted_price=899)]
        offers, count, warning = collect_offers('key', ('first','second'), mock)
        self.assertEqual((len(offers), count, warning), (1, 2, ''))
        self.assertEqual(offers[0].price,899)
        with self.assertRaises(ScanError):
            collect_offers('key', ('first',), lambda k,q: (_ for _ in ()).throw(ScanError('red')))

if __name__ == '__main__': unittest.main()
