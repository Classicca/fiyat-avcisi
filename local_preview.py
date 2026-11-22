"""Explicitly labeled synthetic UI fixture - never used for live publishing."""
from pathlib import Path
import json
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from shutil import copy2
ROOT = Path(__file__).resolve().parent
OUT = ROOT / '.preview'
OUT.mkdir(exist_ok=True)
for f in ('index.html','app.js','styles.css','favicon.svg'):
    copy2(ROOT / 'static' / f, OUT / f)
(OUT / 'data').mkdir(exist_ok=True)
now=int(time.time())
models=[
 ('Klavye · Beyaz Mekanik (ÖRNEK)','keyboard',899,'wireless','mechanical','Beyaz','', 'marketplace'),
 ('Klavye · Kablolu Red Switch (ÖRNEK)','keyboard',649,'wired','mechanical','Siyah','','amazon'),
 ('Klavye · Hall Effect (ÖRNEK)','keyboard',1499,'wired','hall','Siyah','','marketplace'),
 ('Mouse · Beyaz PAW3311 (ÖRNEK)','mouse',699,'wireless','unknown','Beyaz','PAW3311','amazon'),
 ('Mouse · Siyah PAW3395 (ÖRNEK)','mouse',1299,'wired','unknown','Siyah','PAW3395','marketplace'),
]
products=[{'asin':f'EXAMPLE{i:03}', 'id':f'EXAMPLE{i:03}', 'title':title,'category':category,'price':price,
           'currency':'TRY','link':'', 'image':'', 'brand':'Örnek', 'color':color, 'connection':conn,
           'keyboard_type':kind,'sensor':sensor,'seller':'Örnek Satıcı', 'seller_type':seller,
           'checked_at':now,'source':'demo'}
          for i,(title,category,price,conn,kind,color,sensor,seller) in enumerate(models)]
feed={'schema':3,'generated_at':now,'status':{'configured':True,'demo':True,'source':'ÖRNEK VERİ',
      'last_success':now,'last_attempt':now,'last_error':'','warning':'', 'products':len(products)}, 'products':products}
(OUT / 'data' / 'feed.json').write_text(json.dumps(feed,ensure_ascii=False), 'utf-8')
webbrowser.open('http://localhost:8083')
print('Örnek (gerçek olmayan) tasarım: http://localhost:8083')
ThreadingHTTPServer(('127.0.0.1',8083), partial(SimpleHTTPRequestHandler, directory=str(OUT))).serve_forever()
