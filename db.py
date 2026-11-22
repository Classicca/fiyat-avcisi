"""SQLite persistence for verified product offers and observed prices."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from scanner import detect_connectivity


class Store:
    def __init__(self, path):
        self.path = str(Path(path))
        self._init()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _init(self):
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    store TEXT NOT NULL,
                    price REAL NOT NULL,
                    previous_price REAL,
                    original_price REAL,
                    lowest_price REAL NOT NULL,
                    highest_price REAL NOT NULL,
                    link TEXT NOT NULL,
                    image TEXT NOT NULL,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    last_price_change INTEGER,
                    last_drop INTEGER,
                    category TEXT NOT NULL DEFAULT 'keyboard',
                    connectivity TEXT NOT NULL DEFAULT 'unknown',
                    sensor TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    observed_at INTEGER NOT NULL,
                    price REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS prices_product_date ON prices(product_id,observed_at);
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """)
            # Existing v1.1 databases have no category column. Keep their history.
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(products)")}
            if "category" not in columns:
                conn.execute("ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'keyboard'")
            if "sensor" not in columns:
                conn.execute("ALTER TABLE products ADD COLUMN sensor TEXT NOT NULL DEFAULT ''")
            if "connectivity" not in columns:
                conn.execute("ALTER TABLE products ADD COLUMN connectivity TEXT NOT NULL DEFAULT 'unknown'")
                # Backfill old records from their names without discarding price history.
                for row in conn.execute("SELECT id,title FROM products"):
                    conn.execute("UPDATE products SET connectivity=? WHERE id=?",
                                 (detect_connectivity(row["title"]), row["id"]))

    def meta(self):
        with self.connect() as conn:
            return {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM meta")}

    def apply_scan(self, offers, raw_count=0, warning="", now=None):
        """Atomic update: show items present in latest *completed* scan only."""
        now = int(now if now is not None else time.time())
        with self.connect() as conn:
            for offer in offers:
                current = conn.execute("SELECT price,lowest_price,highest_price,first_seen,last_drop,last_price_change FROM products WHERE id=?", (offer.id,)).fetchone()
                if current:
                    previous = float(current["price"])
                    changed = abs(previous - offer.price) >= 0.005
                    conn.execute("""UPDATE products SET title=?,store=?,price=?,previous_price=?,original_price=?,
                        lowest_price=?,highest_price=?,link=?,image=?,last_seen=?,last_price_change=?,last_drop=?,category=?,connectivity=?,sensor=? WHERE id=?""",
                        (offer.title,offer.store,offer.price,previous,offer.original_price,
                         min(current["lowest_price"],offer.price),max(current["highest_price"],offer.price),
                         offer.url,offer.image,now,now if changed else current["last_price_change"],
                         now if changed and offer.price < previous else current["last_drop"],offer.category,offer.connectivity,offer.sensor,offer.id))
                else:
                    changed = True
                    conn.execute("""INSERT INTO products (id,title,store,price,previous_price,original_price,
                        lowest_price,highest_price,link,image,first_seen,last_seen,last_price_change,last_drop,category,connectivity,sensor)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (offer.id,offer.title,offer.store,offer.price,None,offer.original_price,
                         offer.price,offer.price,offer.url,offer.image,now,now,now,None,offer.category,offer.connectivity,offer.sensor))
                if changed:
                    conn.execute("INSERT INTO prices (product_id,observed_at,price) VALUES (?,?,?)",
                                 (offer.id, now, offer.price))
            data = {"last_success":str(now),"last_raw_count":str(raw_count),
                    "last_offer_count":str(len(offers)),"last_warning":warning,"scan_version":"3"}
            conn.executemany("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",data.items())

    def products(self, max_price=1100, mouse_max_price=1000):
        meta = self.meta()
        if not meta.get("last_success"):
            return []
        at = int(meta["last_success"])
        with self.connect() as conn:
            rows = conn.execute("""SELECT * FROM products WHERE last_seen=? AND
                    ((category='keyboard' AND price<=?) OR (category='mouse' AND price<=?))
                    ORDER BY price ASC LIMIT 300""", (at, max_price, mouse_max_price)).fetchall()
        now = int(time.time())
        products = []
        for r in rows:
            p = dict(r)
            p["drop_amount"] = round(max(0, (p["previous_price"] or p["price"]) - p["price"]),2)
            p["is_new"] = now - p["first_seen"] <= 48*3600
            p["price"] = round(p["price"],2)
            p["lowest_price"] = round(p["lowest_price"],2)
            p["highest_price"] = round(p["highest_price"],2)
            products.append(p)
        return products

    def history(self, product_id, limit=40):
        with self.connect() as conn:
            exists = conn.execute("SELECT id FROM products WHERE id=?",(product_id,)).fetchone()
            if not exists:
                return None
            rows = conn.execute("SELECT observed_at,price FROM prices WHERE product_id=? ORDER BY observed_at DESC LIMIT ?", (product_id,limit)).fetchall()
        return [dict(r) for r in reversed(rows)]
