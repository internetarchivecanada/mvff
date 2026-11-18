"""OCR the festival's programme guides on Issuu (one or two per edition, 1978-2026; raw/issuu_map.tsv).

    python3 -m mv.issuu meta      Issuu document page -> image id and page count  (raw/issuu/<doc>.json)
    python3 -m mv.issuu images    page images from Issuu's image server            (raw/issuu/<doc>/page_NNN.jpg)
    python3 -m mv.issuu ocr       Tesseract, 8 at a time                            (raw/issuu/<doc>/page_NNN.txt)

The guides are the festival's own scans, published by the Smith Rafael Film Center / CAFILM account and embedded on
www.mvff.com/mvff-guide-archive/. Everything is cached; re-runs only fetch or OCR what is missing.
"""
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
DIR = RAW / "issuu"
ACCOUNT = "smithrafaelfilmcenter"
S = requests.Session()
S.headers["User-Agent"] = "WaybackLabs-FestivalExplorer/0.1 (Internet Archive research)"


def docs():
    """[(edition, doc id)] from the guide archive map; Issuu ids only (PDF guides are handled with the PDFs)."""
    out = []
    for line in (RAW / "issuu_map.tsv").read_text().splitlines():
        slug, _, rest = line.partition("\t")
        m = re.search(r"mv[vf]f?-?(\d\d)", slug)
        if not m:
            continue
        for tok in rest.split():
            if not tok.startswith("wp-content") and (int(m.group(1)), tok) not in out:
                out.append((int(m.group(1)), tok))
    return sorted(out)


def get(url, binary=False):
    for i in range(5):
        try:
            r = S.get(url, timeout=120)
            if r.status_code == 200:
                return r.content if binary else r.text
            if r.status_code in (403, 404):
                return None
        except requests.RequestException:
            pass
        time.sleep(10 * (i + 1))
    return None


def meta():
    DIR.mkdir(parents=True, exist_ok=True)
    for ed, doc in docs():
        f = DIR / f"{doc}.json"
        if f.exists():
            continue
        t = get(f"https://issuu.com/{ACCOUNT}/docs/{doc}")
        time.sleep(3)
        if not t:
            print("no page:", doc)
            continue
        img = re.findall(r"image\.isu\.pub/([\w-]+)/jpg/page_1", t)
        pc = re.findall(r"pageCount\W+(\d+)", t)
        title = (re.findall(r"<title>(.*?)</title>", t) or [""])[-1].replace(" - Issuu", "").strip()
        rec = {"edition": ed, "year": 1977 + ed, "doc": doc, "image_id": img[0] if img else None,
               "pages": int(pc[0]) if pc else None, "title": title}
        f.write_text(json.dumps(rec))
        print(rec, flush=True)


def images():
    jobs = []
    for f in sorted(DIR.glob("*.json")):
        m = json.loads(f.read_text())
        if not m.get("image_id") or not m.get("pages"):
            continue
        d = DIR / m["doc"]
        d.mkdir(exist_ok=True)
        for n in range(1, m["pages"] + 1):
            out = d / f"page_{n:03d}.jpg"
            if not out.exists():
                jobs.append((f"https://image.isu.pub/{m['image_id']}/jpg/page_{n}.jpg", out))
    print(len(jobs), "page images to fetch", flush=True)

    def one(job):
        url, out = job
        b = get(url, binary=True)
        time.sleep(0.5)
        if b:
            out.write_bytes(b)
        return b is not None

    with cf.ThreadPoolExecutor(4) as ex:
        for k, ok in enumerate(ex.map(one, jobs)):
            if k % 200 == 0:
                print(k, "/", len(jobs), flush=True)


def ocr():
    pages = [p for p in sorted(DIR.glob("*/page_*.jpg")) if not p.with_suffix(".txt").exists()]
    print(len(pages), "pages to OCR", flush=True)

    def one(p):
        r = subprocess.run(["tesseract", str(p), "stdout", "-l", "eng", "--psm", "3"], capture_output=True, text=True)
        p.with_suffix(".txt").write_text(r.stdout)
        return p

    with cf.ThreadPoolExecutor(8) as ex:
        for k, _ in enumerate(ex.map(one, pages)):
            if k % 200 == 0:
                print(k, "/", len(pages), flush=True)


if __name__ == "__main__":
    {"meta": meta, "images": images, "ocr": ocr}[sys.argv[1]]()
