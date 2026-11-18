"""Compare what is live (raw/live) and every programme guide (raw/issuu_map.tsv) against the Wayback Machine.

    python3 -m mv.compare            -> data/inventory.json, data/missing.txt (URLs never captured)

mvff.com and cafilm.org are checked against the full capture lists in raw/cdx_<domain>.txt (one row per
distinct URL key, refreshed by `python3 -m mv.compare --refresh`); other hosts (Issuu, app.mvff.com) are looked
up one by one in the CDX API.
"""
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW, DATA = ROOT / "raw", ROOT / "data"
S = requests.Session()
S.headers["User-Agent"] = "WaybackLabs-FestivalExplorer/0.1 (Internet Archive research)"
CDX = "https://web.archive.org/cdx/search/cdx"
DOMAINS = ("mvff.com", "cafilm.org")


def surt(url):
    """Wayback-style URL key: reversed host without www/port, lower case, sorted query."""
    p = urllib.parse.urlsplit(url.strip())
    host = (p.hostname or "").lower()
    host = re.sub(r"^www\d*\.", "", host)
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    q = "&".join(sorted(p.query.split("&"))) if p.query else ""
    return ",".join(reversed(host.split("."))) + ")" + path.lower() + ("?" + q.lower() if q else "")


def refresh():
    for d in DOMAINS:
        r = S.get(CDX, params={"url": d, "matchType": "domain", "collapse": "urlkey", "limit": 1000000,
                               "fl": "urlkey,timestamp,original,mimetype,statuscode"}, timeout=600)
        (RAW / f"cdx_{d}.txt").write_text(r.text)
        print(d, r.text.count("\n"))
        time.sleep(3)


def load_keys():
    keys = {}
    for d in DOMAINS:
        for line in open(RAW / f"cdx_{d}.txt"):
            k = line.split(" ", 1)[0]
            k = k[:-1] if k.endswith("/") and not k.endswith(")/") else k
            keys[k] = line.split()[1]
    return keys


def one(url):
    for i in range(5):
        try:
            r = S.get(CDX, params={"url": url, "fl": "timestamp", "limit": 1,
                                   "filter": "statuscode:[23].."}, timeout=90)
            if r.status_code == 200:
                return r.text.split()[0] if r.text.strip() else None
            time.sleep(20 * (i + 1))
        except requests.RequestException:
            time.sleep(10 * (i + 1))
    return "error"


def live_items():
    L = RAW / "live"
    for f in sorted(L.glob("*.json")):
        if f.name == "app_films.json":
            for u in json.loads(f.read_text()):
                yield {"url": u, "kind": "film", "source": "app.mvff.com"}
            continue
        site, typ = f.stem.split("_", 1)
        for it in json.loads(f.read_text()):
            if typ == "media":
                mt = it.get("mime_type") or ""
                kind = "pdf" if mt == "application/pdf" else ("image" if mt.startswith("image/") else "file")
                yield {"url": it["source_url"], "kind": kind, "source": f"{site} media", "date": it.get("date")}
            else:
                yield {"url": it["link"], "kind": {"film": "film", "director": "person"}.get(typ, typ.rstrip("s")),
                       "source": f"{site} {typ}", "date": it.get("date"),
                       "title": (it.get("title") or {}).get("rendered")}
    for line in open(RAW / "issuu_map.tsv"):
        slug, _, rest = line.rstrip("\n").partition("\t")
        for tok in rest.split():
            if tok.startswith("wp-content"):
                yield {"url": "https://www.mvff.com/" + tok, "kind": "guide-pdf", "source": slug}
            else:
                yield {"url": f"https://issuu.com/smithrafaelfilmcenter/docs/{tok}", "kind": "guide-issuu",
                       "source": slug}


def main():
    if "--refresh" in sys.argv:
        refresh()
    keys = load_keys()
    items, seen = [], set()
    for it in live_items():
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        host = urllib.parse.urlsplit(it["url"]).hostname or ""
        if host.endswith(DOMAINS) and not host.startswith("app."):
            it["first_capture"] = keys.get(surt(it["url"]))
        else:
            it["first_capture"] = one(it["url"])
            time.sleep(1)
        items.append(it)
    DATA.mkdir(exist_ok=True)
    (DATA / "inventory.json").write_text(json.dumps(items, ensure_ascii=False, indent=0))
    missing = [i for i in items if not i["first_capture"] and i["kind"] != "image"]
    (DATA / "missing.txt").write_text("".join(i["url"] + "\n" for i in missing))
    from collections import Counter
    c = Counter((i["kind"], bool(i["first_capture"])) for i in items)
    for (k, cap), n in sorted(c.items()):
        print(f"{k:12s} {'archived' if cap else 'MISSING':9s} {n}")
    print("missing (excluding images):", len(missing))


if __name__ == "__main__":
    main()
