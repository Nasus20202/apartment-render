"""Download the CC0 / public-domain assets listed in data/assets.json into assets/ (idempotent).

    python3 scripts/fetch_assets.py

Layout:
    assets/polyhaven/models/<id>/<id>_<res>.blend (+ textures/)
    assets/polyhaven/hdris/<id>_<res>.hdr
    assets/ambientcg/<id>/<id>_<res>_<Map>.jpg
    assets/images/<key>.jpg                     (Wikimedia Commons, public domain)
"""

import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
MANIFEST = json.loads((ROOT / "data" / "assets.json").read_text())
UA = {"User-Agent": "apartment-render/1.0 (personal visualization project)"}


def get(url, attempts=4):
    for i in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except OSError:  # covers URLError and SSL EOFs, which happen now and then on the CDNs
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))


def save(url, dest: Path):
    if dest.exists() and dest.stat().st_size > 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(get(url))
    tmp.rename(dest)
    return True


def polyhaven_model(asset_id, res):
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset_id}"))
    blend = files["blend"][res]["blend"]
    base = ASSETS / "polyhaven" / "models" / asset_id
    n = int(save(blend["url"], base / f"{asset_id}_{res}.blend"))
    for rel, info in blend.get("include", {}).items():
        n += save(info["url"], base / rel)
    return f"model {asset_id}: {n} new file(s)"


def polyhaven_hdri(asset_id, res):
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset_id}"))
    new = save(
        files["hdri"][res]["hdr"]["url"], ASSETS / "polyhaven" / "hdris" / f"{asset_id}_{res}.hdr"
    )
    return f"hdri {asset_id}: {'downloaded' if new else 'cached'}"


def ambientcg(asset_id, res):
    dest = ASSETS / "ambientcg" / asset_id
    if dest.exists() and any(dest.glob(f"*_{res}_Color.*")):
        return f"material {asset_id}: cached"
    data = get(f"https://ambientcg.com/get?file={asset_id}_{res}.zip")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            # Keep the texture maps only; skip previews, .mtlx, .usda and the like
            if name.lower().endswith((".jpg", ".png")) and f"_{res}_" in name:
                (dest / Path(name).name).write_bytes(z.read(name))
    return f"material {asset_id}: downloaded"


def commons_image(key, title, width=1600):
    dest = ASSETS / "images" / f"{key}.jpg"
    if dest.exists() and dest.stat().st_size > 0:
        return f"image {key}: cached"
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": width,
        }
    )
    pages = json.loads(get("https://commons.wikimedia.org/w/api.php?" + q))["query"]["pages"]
    info = next(iter(pages.values()))["imageinfo"][0]
    save(info.get("thumburl") or info["url"], dest)
    return f"image {key}: downloaded"


def main():
    jobs = [(polyhaven_model, k, v["res"]) for k, v in MANIFEST["polyhaven_models"].items()]
    jobs += [(polyhaven_hdri, k, v["res"]) for k, v in MANIFEST["polyhaven_hdris"].items()]
    jobs += [(ambientcg, k, v["res"]) for k, v in MANIFEST["ambientcg"].items()]
    jobs += [(commons_image, k, v["commons"]) for k, v in MANIFEST.get("images", {}).items()]
    failed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn, i, r): i for fn, i, r in jobs}
        for f, asset_id in futures.items():
            try:
                print(f.result())
            except Exception as e:  # report every failure, then exit non-zero
                failed += 1
                print(f"FAILED {asset_id}: {e}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
