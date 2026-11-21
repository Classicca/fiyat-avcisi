"""Create the public, safe-to-publish static GitHub Pages artifact."""
from pathlib import Path
from shutil import copy2, rmtree

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'public'
FILES = ('index.html', 'app.js', 'styles.css', 'favicon.svg')


def build_site(out: Path = OUT):
    if out.exists():
        rmtree(out)
    out.mkdir(parents=True)
    for filename in FILES:
        copy2(ROOT / 'static' / filename, out / filename)
    data_dir = out / 'data'
    data_dir.mkdir()
    copy2(ROOT / 'data' / 'feed.json', data_dir / 'feed.json')
    (out / '.nojekyll').touch()
    return out


if __name__ == '__main__':
    print('Hazır:', build_site())
