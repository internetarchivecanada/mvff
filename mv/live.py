"""Inventory of what is live now on mvff.com, cafilm.org and app.mvff.com -> raw/live/*.json.

    python3 -m mv.live

WordPress REST lists (pages, posts, film, director, media incl. every uploaded PDF) and the 2026 browse page.
Both sites ask for a 10-second crawl delay (robots.txt); every request here waits 10 s.
"""
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "live"
S = requests.Session()
S.headers["User-Agent"] = "WaybackLabs-FestivalExplorer/0.1 (Internet Archive research)"
DELAY = 10
FIELDS = "id,date,modified,slug,link,title,type,mime_type,source_url,media_type"


def get(url, **params):
    for i in range(5):
        r = S.get(url, params=params, timeout=60)
        time.sleep(DELAY)
        if r.status_code == 200:
            return r
        if r.status_code in (400, 404):
            return None
        time.sleep(30 * (i + 1))
    r.raise_for_status()


def wp_all(site, base):
    out, page = [], 1
    while True:
        r = get(f"https://{site}/wp-json/wp/v2/{base}", per_page=100, page=page, _fields=FIELDS)
        if r is None:
            break
        items = r.json()
        out += items
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for site, bases in (("www.mvff.com", ["pages", "posts", "film", "director", "media"]),
                        ("www.cafilm.org", ["pages", "posts", "portfolio", "media"])):
        for b in bases:
            f = OUT / f"{site.removeprefix('www.')}_{b}.json"
            if f.exists():
                continue
            items = wp_all(site, b)
            f.write_text(json.dumps(items, ensure_ascii=False))
            print(site, b, len(items), flush=True)
    r = get("https://app.mvff.com/browse")
    films = sorted(set(re.findall(r'href="(/film/[a-z0-9-]+)"', r.text)) | set(
        "/film/" + s for s in re.findall(r'/drive_serve/([a-z0-9-]+)/0-600', r.text)))
    (OUT / "app_films.json").write_text(json.dumps(["https://app.mvff.com" + p for p in films]))
    print("app films", len(films))


if __name__ == "__main__":
    main()
