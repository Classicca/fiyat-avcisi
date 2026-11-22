import tempfile
import unittest
from pathlib import Path
from db import Store
from scanner import Offer

class StorageTests(unittest.TestCase):
    def test_save_and_drops_and_budget_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'offers.db')
            item = Offer('abc', 'Kablosuz Gaming Klavye', 'Mağaza', 1300, None, 'https://example.com', '')
            store.apply_scan([item], 1, now=1000)
            self.assertEqual(len(store.products(1100)), 0)
            self.assertEqual(len(store.products(1300)), 1)  # boundary inclusive
            changed = Offer('abc', item.title, item.store, 1099, None, item.url, '')
            store.apply_scan([changed], 1, now=2000)
            result = store.products(1100)
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['drop_amount'],201)
            self.assertEqual(result[0]['lowest_price'],1099)
            self.assertEqual(len(store.products(1098.99)), 0)
            self.assertEqual(len(store.history('abc')), 2)
            store.apply_scan([changed],1,now=3000)
            self.assertEqual(len(store.history('abc')), 2)
            self.assertIsNone(store.history('not-found'))

    def test_separate_category_price_caps_and_old_database(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'offers.db'
            # Simulate a v1.1 table with the original column set.
            with sqlite3.connect(path) as conn:
                conn.execute("""CREATE TABLE products (id TEXT PRIMARY KEY, title TEXT NOT NULL, store TEXT NOT NULL,
                price REAL NOT NULL, previous_price REAL, original_price REAL, lowest_price REAL NOT NULL,
                highest_price REAL NOT NULL, link TEXT NOT NULL, image TEXT NOT NULL, first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL, last_price_change INTEGER, last_drop INTEGER)""")
            store = Store(path)
            with store.connect() as conn:
                self.assertIn('category', [c['name'] for c in conn.execute('PRAGMA table_info(products)')])
                self.assertIn('connectivity', [c['name'] for c in conn.execute('PRAGMA table_info(products)')])
            offers = [
                Offer('kbd1100', 'Wireless Gaming Klavye', 'A', 1100, None, 'https://example.com/1', ''),
                Offer('kbd1101', 'Wireless Gaming Klavye', 'A', 1101, None, 'https://example.com/2', ''),
                Offer('mouse1000', 'Kablolu Gaming Mouse', 'B', 1000, None, 'https://example.com/3', '', 'mouse', 'wired'),
                Offer('mouse1001', 'Gaming Mouse', 'B', 1001, None, 'https://example.com/4', '', 'mouse'),
            ]
            store.apply_scan(offers, now=5000)
            visible = store.products()
            self.assertEqual({row['id'] for row in visible}, {'kbd1100', 'mouse1000'})
            self.assertEqual({row['category'] for row in visible}, {'keyboard', 'mouse'})
            self.assertEqual(next(row['connectivity'] for row in visible if row['category'] == 'mouse'), 'wired')
            self.assertEqual(store.meta()['scan_version'], '3')

    def test_migrate_existing_v12_connectivity(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'v12.db'
            with sqlite3.connect(path) as conn:
                conn.execute('''CREATE TABLE products (id TEXT PRIMARY KEY, title TEXT NOT NULL,
                  store TEXT NOT NULL, price REAL NOT NULL, previous_price REAL,
                  original_price REAL, lowest_price REAL NOT NULL, highest_price REAL NOT NULL,
                  link TEXT NOT NULL, image TEXT NOT NULL, first_seen INTEGER NOT NULL,
                  last_seen INTEGER NOT NULL, last_price_change INTEGER, last_drop INTEGER,
                  category TEXT NOT NULL DEFAULT 'keyboard')''')
                conn.execute('''INSERT INTO products (id,title,store,price,lowest_price,highest_price,link,image,first_seen,last_seen,category)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)''', ('old-1', 'Bluetooth RGB Gaming Keyboard', 'A', 900, 900, 900, 'https://example.com', '', 1, 1, 'keyboard'))
            store = Store(path)
            with store.connect() as conn:
                row = conn.execute('SELECT connectivity FROM products WHERE id=?', ('old-1',)).fetchone()
                self.assertEqual(row['connectivity'], 'wireless')
            # Re-opening does not destroy historic records.
            self.assertEqual(Store(path).connect().execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)

    def test_last_success_filters_old_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp)/'offers.db')
            item = Offer('x','a','b',999,None,'https://example.com','')
            store.apply_scan([item], now=3000)
            store.apply_scan([],now=4000)
            self.assertEqual(store.products(1100),[])

    def test_sensor_persistence_in_existing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            db = Store(Path(directory) / 'sensors.db')
            db.apply_scan([Offer('paw', 'Gaming Mouse PAW3311', 'Store', 1499, None,
                                 'https://example.com/m', '', 'mouse', 'wireless', 'PAW3311')], now=1795290000)
            rows = db.products(3000, 3000)
            self.assertEqual(rows[0]['sensor'], 'PAW3311')

if __name__ == '__main__': unittest.main()
