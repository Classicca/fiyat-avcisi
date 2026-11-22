"""Approved retailer allowlist regressions (no live HTTP requests)."""
import unittest
from cloud_publish import empty_state, public_feed
from merchants import APPROVED_RETAILERS, trusted_retailer
from scanner import parse_offer, parse_product_stores, product_model_key


class ApprovedRetailerTests(unittest.TestCase):
    def test_all_nine_platforms_and_subdomains(self):
        self.assertEqual(len(APPROVED_RETAILERS), 9)
        for domain, label in APPROVED_RETAILERS:
            with self.subTest(domain=domain):
                self.assertEqual(trusted_retailer('https://' + domain + '/item'), label)
                self.assertEqual(trusted_retailer('https://www.' + domain + '/item'), label)
                self.assertEqual(trusted_retailer('https://www.' + domain.upper() + '/item'), label)

    def test_reject_comparators_unknowns_and_lookalikes(self):
        blocked = [
            'https://epey.com/p', 'https://akakce.com/p',
            'https://turkish-e-market.com/p', 'https://google.com/shopping?url=x',
            'https://trendyol.com.evil.example/p', 'https://evil-trendyol.com/p',
            'https://amazon.com/p', 'http://trendyol.com/p',
            'https://trendyol.com@evil.example/p', 'javascript:alert(1)',
            'https://trendyol.com:evil/p',
        ]
        for link in blocked:
            with self.subTest(link=link):
                self.assertFalse(trusted_retailer(link))

    def test_ignore_untrusted_seller_name_and_missing_direct_offer_url(self):
        base = {'title': 'James Donkey JDK99 Kablosuz Gaming Klavye', 'extracted_price': 799}
        self.assertIsNone(parse_offer(dict(base, source='Trendyol', link='https://unknownstore.com/p')))
        self.assertIsNone(parse_offer(dict(base, source='Trendyol', link='https://www.google.com/shopping/product/1')))
        approved = parse_offer(dict(base, source='Unknown reseller', link='https://www.incehesap.com/p'))
        self.assertEqual(approved.store, 'İncehesap')
        self.assertEqual(approved.price, 799)

    def test_merchant_link_can_fallback_to_second_product_link(self):
        offer = parse_offer({
            'title':'Wireless RGB Gaming Klavye', 'source':'Trendyol', 'extracted_price':850,
            'link':'https://www.google.com/shopping/product/123',
            'product_link':'https://www.trendyol.com/keyboard/p',
        })
        self.assertIsNotNone(offer)
        self.assertEqual(offer.store, 'Trendyol')
        self.assertEqual(offer.url, 'https://www.trendyol.com/keyboard/p')

    def test_price_anomalies_are_not_promoted(self):
        row = dict(title='Kablolu RGB Gaming Klavye', source='Trendyol',
                   link='https://www.trendyol.com/item', price='899,00 TL', extracted_price=71.06)
        self.assertIsNone(parse_offer(row))
        self.assertIsNotNone(parse_offer(dict(row, extracted_price=899)))
        self.assertIsNone(parse_offer(dict(row, price='3 taksit 71,06 TL', extracted_price=None)))

    def test_seller_detail_rejects_unapproved_store(self):
        parent = parse_offer(dict(title='James Donkey JDK99 RGB Gaming Klavye',
                                  link='https://www.trendyol.com/jdk99', extracted_price=899,
                                  product_id='1234567890123456'))
        details = {'product_results': {'stores': [
            {'name': 'İncehesap', 'title': parent.title, 'price':'809 TL',
             'link':'https://www.incehesap.com/jdk99'},
            {'name':'Unknown Shop', 'title':parent.title, 'price':'71,06 TL',
             'link':'https://unverified-store.example/jdk99'},
        ]}}
        offers = parse_product_stores(details, parent)
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].price, 809)

    def test_historic_unapproved_offers_never_enter_new_public_feed(self):
        now = 1795290000
        state = empty_state()
        for i, link in enumerate(('https://unknown.example/p', 'https://www.incehesap.com/p')):
            state['products'][str(i)] = dict(id=str(i), title='James Donkey JDK99 RGB Gaming Klavye',
              store='Wrong seller name', price=700+i*100, link=link, image='', category='keyboard',
              first_seen=now, last_seen=now, model_key='keyboard|james donkey|jdk99')
        state['active']['keyboard'] = ['0', '1']
        feed = public_feed(state, True, now)
        self.assertEqual(len(feed['products']), 1)
        self.assertEqual(feed['products'][0]['store'], 'İncehesap')
        self.assertEqual(feed['products'][0]['price'], 800)
        self.assertEqual(feed['status']['approved_retailers'].__len__(), 9)


if __name__ == '__main__':
    unittest.main()
