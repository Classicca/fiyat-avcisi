"""Fiyat Avcısı: dependency-free local web app and scheduled product discovery.

Usage:
    python server.py                 # needs SerpApi key via UI or SERPAPI_KEY
    python server.py --demo          # clearly labeled fictional demo offers
"""
from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from db import Store
from merchants import trusted_retailer
from scanner import ScanError, collect_offers, detect_connectivity

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
KEYBOARD_BUDGET = 1100
MOUSE_BUDGET = 1000
INTERVAL_MINUTES = max(30, int(os.getenv("SCAN_INTERVAL_MINUTES", "1440")))
SETTINGS_FILE = BASE / "settings.local.json"
DB_FILE = BASE / "fiyat-avcisi.db"

DEMO_NAMES = [
    ("keyboard", "ÖRNEK · Nova K68 Kablosuz RGB Gaming Klavye", "Örnek Mağaza A", 849, 1099, 899, True),
    ("keyboard", "ÖRNEK · Vector 60 Kablolu Mekanik Oyuncu Klavyesi", "Örnek Mağaza B", 999, 1249, 1059, False),
    ("keyboard", "ÖRNEK · Phantom 87 2.4GHz RGB Gaming Keyboard", "Örnek Mağaza C", 1099, 1399, 1199, True),
    ("keyboard", "ÖRNEK · Pixel TKL Kablolu Mekanik Klavye", "Örnek Mağaza D", 769, 899, 769, False),
    ("mouse", "ÖRNEK · Falcon G7 Kablolu RGB Gaming Mouse", "Örnek Mağaza E", 599, 799, 699, True),
    ("mouse", "ÖRNEK · Vortex 2.4 GHz Kablosuz Oyuncu Fare", "Örnek Mağaza B", 949, 1199, 1029, False),
    ("mouse", "ÖRNEK · Blitz Pro Kablolu 12000 DPI Gaming Mouse", "Örnek Mağaza F", 799, 999, 799, False),
    ("mouse", "ÖRNEK · Lynx Kablosuz RGB Oyuncu Mouse", "Örnek Mağaza A", 399, 549, 479, True),
]


def demo_products():
    now = int(time.time())
    items = []
    for i, (category, name, store, price, old, prev, newer) in enumerate(DEMO_NAMES):
        items.append(dict(id=f"demo-{i}", category=category, title=name, store=store, price=price, previous_price=prev,
                          original_price=old, lowest_price=price, highest_price=max(old, prev),
                          link="", image="", connectivity=detect_connectivity(name), first_seen=now-(1200 if newer else 5*86400),
                          last_seen=now, drop_amount=max(0, prev-price), is_new=newer))
    return items


class App:
    def __init__(self, demo=False):
        self.demo = demo
        self.db = Store(DB_FILE)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.scanning = False
        self.last_error = ""
        self.last_attempt = 0.0
        self.force_next = self.db.meta().get("scan_version") != "3"
        self.config = self.read_config()
        if not demo:
            threading.Thread(target=self.scheduler, name="fiyat-tarama", daemon=True).start()

    def read_config(self):
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def api_key(self):
        return (os.getenv("SERPAPI_KEY", "") or self.config.get("serpapi_key", "")).strip()

    def is_configured(self):
        return bool(self.api_key())

    def set_api_key(self, key):
        if os.getenv("SERPAPI_KEY"):
            raise ValueError("API anahtarı ortam değişkeniyle ayarlanmış; arayüzden değiştirilemez.")
        if not isinstance(key, str) or not (16 <= len(key.strip()) <= 300) or re.search(r"\s", key.strip()):
            raise ValueError("Geçerli bir SerpApi anahtarı gir (en az 16 karakter).")
        key = key.strip()
        # This local file holds a secret; it is intentionally never sent to the browser.
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"serpapi_key":key}, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(SETTINGS_FILE)
        with self.lock:
            self.config = {"serpapi_key": key}
            self.force_next = True
        self.wake.set()

    def scheduler(self):
        while True:
            self.wake.wait(timeout=30)
            self.wake.clear()
            key = self.api_key()
            if not key:
                continue
            with self.lock:
                if self.scanning:
                    continue
                meta = self.db.meta()
                last_success = int(meta.get("last_success") or 0)
                due_regular = time.time() - last_success >= INTERVAL_MINUTES * 60
                due_retry = time.monotonic() - self.last_attempt >= 30 * 60
                requested = self.force_next
                should_scan = (requested or due_regular) and (requested or not self.last_attempt or due_retry)
                if not should_scan:
                    continue
                self.force_next = False
                self.scanning = True
                self.last_attempt = time.monotonic()
            try:
                offers, raw_count, warning = collect_offers(key)
                self.db.apply_scan(offers, raw_count, warning)
                with self.lock:
                    self.last_error = ""
            except (ScanError, OSError) as exc:
                with self.lock:
                    self.last_error = str(exc)
            except Exception:
                with self.lock:
                    self.last_error = "Tarama sırasında beklenmeyen bir hata oluştu."
            finally:
                with self.lock:
                    self.scanning = False

    def request_scan(self):
        if self.demo:
            return False, "Örnek modda canlı tarama yapılmaz."
        if not self.is_configured():
            return False, "Önce SerpApi anahtarını ekle."
        with self.lock:
            if self.scanning:
                return False, "Tarama zaten devam ediyor."
            if self.last_attempt and time.monotonic() - self.last_attempt < 60:
                return False, "Yeni tarama için en az 60 saniye bekle."
            self.force_next = True
        self.wake.set()
        return True, "Tarama başlatılıyor."

    def products(self):
        if self.demo:
            return demo_products()
        # Filter historic local SQLite entries just like GitHub Pages JSON.
        visible = []
        for row in self.db.products(999999, 999999):
            retailer = trusted_retailer(row.get('link', ''))
            if retailer:
                visible.append({**row, 'store': retailer})
        return visible

    def status(self):
        meta = {} if self.demo else self.db.meta()
        products = self.products()
        last_success = int(meta.get("last_success") or 0)
        with self.lock:
            scanning = self.scanning
            error = self.last_error
        configured = self.is_configured() or self.demo
        return dict(
            app="Fiyat Avcısı", max_price=KEYBOARD_BUDGET, keyboard_max_price=KEYBOARD_BUDGET,
            mouse_max_price=MOUSE_BUDGET, configured=configured, demo=self.demo,
            scanning=scanning, last_error=error, warning=meta.get("last_warning", ""),
            last_success=(last_success if last_success else None),
            next_scan=(last_success + INTERVAL_MINUTES * 60 if last_success else None),
            scan_interval_minutes=INTERVAL_MINUTES,
            product_count=len(products), store_count=len(set(p["store"] for p in products)),
            drop_count=sum(bool(p["drop_amount"]) for p in products),
            new_count=sum(bool(p["is_new"]) for p in products),
            raw_result_count=int(meta.get("last_raw_count") or 0),
        )


class Handler(BaseHTTPRequestHandler):
    app: App

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.client_address[0]} - {fmt % args}")

    def json(self, obj, status=HTTPStatus.OK):
        content = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/status":
            return self.json(self.app.status())
        if path == "/api/products":
            return self.json({"products":self.app.products()})
        if path == "/api/history":
            item_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            if self.app.demo and re.fullmatch(r"demo-[0-7]", item_id):
                product = demo_products()[int(item_id[-1])]
                now = int(time.time())
                return self.json({"history":[{"observed_at":now-(6-i)*86400,"price":p} for i,p in enumerate([
                    product["highest_price"], product["highest_price"], product["previous_price"],
                    product["previous_price"], product["price"], product["price"],product["price"]]) ]})
            if not re.fullmatch(r"[a-f0-9]{24}", item_id):
                return self.json({"error":"Ürün bulunamadı."}, 404)
            history = self.app.db.history(item_id)
            if history is None:
                return self.json({"error":"Ürün bulunamadı."}, 404)
            return self.json({"history":history})
        static_files = {"/":"index.html", "/index.html":"index.html",
                        "/styles.css":"styles.css", "/app.js":"app.js", "/favicon.svg":"favicon.svg"}
        filename = static_files.get(path)
        if not filename:
            return self.json({"error":"Sayfa bulunamadı."}, 404)
        mime = ("text/html; charset=utf-8" if filename.endswith("html") else
                "text/css; charset=utf-8" if filename.endswith("css") else
                "text/javascript; charset=utf-8" if filename.endswith("js") else "image/svg+xml")
        try:
            body = (STATIC / filename).read_bytes()
        except OSError:
            return self.json({"error":"Dosya okunamadı."}, 500)
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/api/configure", "/api/scan"):
            return self.json({"error":"Bulunamadı."}, 404)
        # Admin endpoints are meant ONLY for a locally installed app, not a public website.
        origin = self.headers.get("Origin", "")
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return self.json({"error":"Yalnızca yerel bağlantılara izin verilir."}, 403)
        if origin:
            try:
                p = urlsplit(origin)
                host = p.hostname or ""
            except ValueError:
                host = ""
            if host not in ("127.0.0.1", "localhost"):
                return self.json({"error":"İzin verilmeyen istek kaynağı."}, 403)
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json" or self.headers.get("X-Local-Action") != "1":
            return self.json({"error":"Geçersiz istek."}, 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 4096:
                raise ValueError("Boyut hatalı.")
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError("Beklenmeyen içerik.")
        except (ValueError, UnicodeDecodeError):
            return self.json({"error":"Geçersiz JSON."}, 400)
        if path == "/api/configure":
            try:
                self.app.set_api_key(body.get("api_key"))
            except ValueError as exc:
                return self.json({"error":str(exc)}, 400)
            except OSError:
                return self.json({"error":"Ayar dosyasına yazılamadı."}, 500)
            return self.json({"ok":True,"message":"Anahtar kaydedildi; otomatik tarama başlatılıyor."})
        ok, msg = self.app.request_scan()
        return self.json({"ok":ok,"message":msg}, 200 if ok else 409)


def main():
    arg = argparse.ArgumentParser(description="Fiyat Avcısı - otomatik gaming klavye ve mouse takibi")
    arg.add_argument("--demo", action="store_true", help="Gerçek ürün içermeyen açıkça etiketlenmiş örnek görünüm")
    arg.add_argument("--port", type=int, default=8000)
    arg.add_argument("--host", default="127.0.0.1", help="Yerel kullanım için 127.0.0.1 (varsayılan)")
    args = arg.parse_args()
    app = App(demo=args.demo)
    Handler.app = app
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"\nFiyat Avcısı açıldı: http://{args.host}:{args.port}\n"
          f"Mod: {'ÖRNEK / KURGUSAL VERİ' if args.demo else 'CANLI (API anahtarı gerekli)'}\n"
          f"Klavye: {KEYBOARD_BUDGET} TL | Mouse: {MOUSE_BUDGET} TL | Tarama aralığı: {INTERVAL_MINUTES} dakika\n"
          "Durdurmak için Ctrl+C.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatılıyor...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
