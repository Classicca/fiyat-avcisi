"""Static GitHub Pages builder. Never publishes a preview as real prices."""
from pathlib import Path
from shutil import copy2, rmtree
import json
ROOT = Path(__file__).resolve().parent

def build_site(out=None):
    out = Path(out or ROOT / 'public')
    src = ROOT / 'data' / 'feed.json'
    if not src.exists():
        from cloud_publish import sync
        sync()
    feed = json.loads(src.read_text('utf-8'))
    if feed.get('schema') != 3 or feed.get('status', {}).get('demo'):
        raise ValueError('Gerçek GitHub yayınında sadece v3 Amazon feed.json kullanılabilir.')
    if out.exists(): rmtree(out)
    out.mkdir(parents=True)
    for name in ['index.html', 'styles.css', 'app.js', 'favicon.svg']:
        copy2(ROOT / 'static' / name, out / name)
    (out / 'data').mkdir()
    copy2(src, out / 'data' / 'feed.json')
    (out / '.nojekyll').touch()
    return out

if __name__ == '__main__':
    print('Yayın klasörü:', build_site())
