"""Find a poster for each film and save it to assets/img/poster/<film id>.jpg.

Sources, in order:
  1. English Wikipedia: the lead image of the film's article (for films, the theatrical poster). The article must
     mention one of the film's directors in its introduction, or call itself a documentary/film with a matching title.
  2. Wikidata: P3383 (film poster) or P18 (image) on a documentary/film item whose director matches.
  (The festival's own film images are 16:9 stills, so they are not used.)
  3. Posters found by searching the web (data/poster_candidates/batch*-output.json), checked by eye.

Writes data/posters.json: {film id: {"src", "source", "page", "credit"}}. Re-runs keep earlier results
(delete an entry, or add the film id to data/bad_posters.txt, to drop it).

    python3 -m mv.posters
"""
import json
import re
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUB = ROOT / "assets"     # copied into public/ by mv.site (which rebuilds public/ from scratch)
CACHE = ROOT / "raw" / "posters"
AUTO = ("wikipedia", "wikidata")
UA = "MillValleyFilmFestivalExplorer/1.0 (Internet Archive Wayback Machine Labs; https://wayback-labs.sf.archive.org/mvff/)"


def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            if i == tries - 1:
                print("  fail", url[:120], e)
                return None
            time.sleep(3 * (i + 1))


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()


def norm_title(t):
    t = fold(t)
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"^(the|a|an) ", "", t.strip())


def surnames(names):
    out = []
    for n in names:
        parts = fold(n).replace("-", " ").split()
        if parts:
            out.append(parts[-1])
    return [s for s in out if len(s) > 2]


def wiki_candidates(title, year, dirs):
    q = f'"{title}" film' + (f" {dirs[0]}" if dirs else "")
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": q, "gsrlimit": "6",
              "prop": "pageimages|extracts|pageprops", "piprop": "original|name", "pilicense": "any",
              "exintro": "1", "explaintext": "1", "exlimit": "max", "redirects": "1"}
    d = get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params))
    pages = (d or {}).get("query", {}).get("pages", {})
    return sorted(pages.values(), key=lambda p: p.get("index", 99))


def wiki_match(f, dirnames):
    title = f["title"]
    nt = norm_title(title)
    sn = surnames(dirnames)
    for p in wiki_candidates(title, f.get("film_year"), dirnames):
        pt = norm_title(re.sub(r"\s*\((?:\d{4} )?(?:documentary )?film\)$", "", p["title"]))
        ext = fold(p.get("extract", ""))
        title_ok = pt == nt or (len(nt) > 8 and (pt.startswith(nt) or nt.startswith(pt)) and min(len(pt), len(nt)) > 8)
        if not title_ok:
            continue
        dir_ok = any(re.search(r"\b" + re.escape(s) + r"\b", ext) for s in sn)
        kind_ok = bool(re.search(r"\b(documentary|film)\b", ext[:400]))
        year_ok = not f.get("film_year") or any(str(y) in ext for y in (f["film_year"] - 1, f["film_year"], f["film_year"] + 1))
        if not (dir_ok if sn else (kind_ok and year_ok)):
            continue
        img = p.get("original", {}).get("source")
        if not img or img.lower().endswith(".svg"):
            continue
        return {"src": img, "source": "wikipedia", "page": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_")),
                "credit": f"Wikipedia: {p['title']}", "file": p.get("pageimage")}
    return None


def wikidata_match(f, dirnames):
    title = f["title"]
    d = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "wbsearchentities", "search": title, "language": "en", "type": "item", "limit": "7", "format": "json"}))
    ids = [x["id"] for x in (d or {}).get("search", []) if norm_title(x.get("label", "")) == norm_title(title)]
    if not ids:
        return None
    e = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|labels", "languages": "en", "format": "json"}))
    sn = surnames(dirnames)
    for qid, ent in ((e or {}).get("entities") or {}).items():
        cl = ent.get("claims", {})
        inst = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in cl.get("P31", [])}
        if not inst & {"Q11424", "Q93204", "Q24862", "Q506240", "Q202866"}:  # film, documentary, short, TV film, animated
            continue
        dir_ids = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in cl.get("P57", [])]
        if sn and dir_ids:
            dl = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "wbgetentities", "ids": "|".join(i for i in dir_ids if i)[:400], "props": "labels", "languages": "en", "format": "json"}))
            labels = " ".join(fold(v.get("labels", {}).get("en", {}).get("value", "")) for v in ((dl or {}).get("entities") or {}).values())
            if not any(s in labels for s in sn):
                continue
        elif sn:
            continue
        for prop in ("P3383", "P18"):
            for c in cl.get(prop, []):
                fn = c["mainsnak"].get("datavalue", {}).get("value")
                if fn:
                    src = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn.replace(" ", "_"))
                    return {"src": src, "source": "wikidata", "page": f"https://www.wikidata.org/wiki/{qid}",
                            "credit": f"Wikimedia Commons: {fn}", "file": fn}
    return None


def thumb(url):
    """upload.wikimedia.org original -> 330px standard thumbnail (kinder to the image servers)."""
    url = url.split("?")[0]
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/[a-z]+)/([0-9a-f])/([0-9a-f]{2})/(.+)$", url)
    if not m:
        return url
    name = m.group(4)
    t = f"{m.group(1)}/thumb/{m.group(2)}/{m.group(3)}/{name}/330px-{name}"
    return t + ".png" if name.lower().endswith((".svg", ".tif", ".tiff")) else t


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    for attempt in range(5):
        try:
            req = urllib.request.Request(urllib.parse.quote(url, safe=":/?=&%~+@!$,;"), headers={"User-Agent": UA})
            dest.write_bytes(urllib.request.urlopen(req, timeout=90).read())
            time.sleep(2)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20 * (attempt + 1))
                continue
            if e.code in (400, 404) and "/thumb/" in url:  # image smaller than 330px: use the original
                url = re.sub(r"/thumb/(.+)/[^/]+$", r"/\1", url)
                continue
            print("  fail", url[:120], e)
            return False
        except Exception as e:
            print("  fail", url[:120], e)
            return False
    print("  gave up", url[:120])
    return False


def main():
    d = json.load(open(DATA / "festival.json"))
    P = d["people"]
    out = json.load(open(DATA / "posters.json")) if (DATA / "posters.json").exists() else {}
    bad, bad_auto = set(), set()
    if (DATA / "bad_posters.txt").exists():
        lines = [l.split() for l in (DATA / "bad_posters.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
        bad = {l[0] for l in lines if len(l) == 1}           # no poster at all for this film
        bad_auto = {l[1] for l in lines if len(l) == 2 and l[0] == "auto"}  # the automatic match was wrong
    CACHE.mkdir(parents=True, exist_ok=True)
    (PUB / "img" / "poster").mkdir(parents=True, exist_ok=True)
    films = sorted(d["films"].values(), key=lambda f: f["id"])
    import sys
    search = "--download-only" not in sys.argv     # --download-only: just (re)convert the posters already found
    for i, f in enumerate(films if search else []):
        fid = f["id"]
        if fid in bad:
            if fid in out:
                out.pop(fid)
                (PUB / "img" / "poster" / f"{fid}.jpg").unlink(missing_ok=True)
            if fid not in out:
                continue
        if fid in out or fid in bad_auto:
            continue
        dirnames = [P[x]["name"] for x in f.get("directors", []) if x in P]
        if f.get("is_short") and not dirnames:
            continue                     # untitled youth-reel shorts and the like: nothing to match on
        hit = wiki_match(f, dirnames) or wikidata_match(f, dirnames)
        time.sleep(0.3)
        if hit:
            out[fid] = hit
            print(f"{i+1}/{len(films)} {f['title']} <- {hit['source']} {hit.get('file') or ''}", flush=True)
        if i % 100 == 0:
            json.dump(out, open(DATA / "posters.json", "w"), indent=1, ensure_ascii=False, sort_keys=True)
            print(f"-- {i+1}/{len(films)} checked, {len(out)} found", flush=True)
    # posters found by searching the web (data/poster_candidates/batch*-output.json), checked by eye
    import glob
    for fn in sorted(glob.glob(str(DATA / "poster_candidates" / "batch*-output.json"))):
        for c in json.load(open(fn)):
            if c.get("id") in d["films"] and c["id"] not in bad and c.get("image_url") and (c["id"] not in out or out[c["id"]]["source"] == "festival") and c.get("confidence") in ("high", "medium"):
                out[c["id"]] = {"src": c["image_url"], "source": "web", "page": c.get("page_url"),
                                "credit": c.get("source") or "the web", "kind": c.get("kind") or "poster"}
    # download + resize
    for fid, h in list(out.items()):
        if fid not in out:
            continue
        ext = re.sub(r"[^a-z]", "", h["src"].rsplit(".", 1)[-1].split("?")[0].lower())[:4] or "img"
        src = thumb(h["src"]) if h["source"].startswith("wikipedia") else h["src"]
        import hashlib
        raw = CACHE / f"{fid}-{hashlib.md5(src.encode()).hexdigest()[:8]}.{ext}"
        dest = PUB / "img" / "poster" / f"{fid}.jpg"
        if dest.exists() and h.get("img_src") != src:
            dest.unlink()  # the poster for this film changed source
        h["img_src"] = src
        if h["source"] == "wikidata":
            src += "?width=600"
        if not fetch(src, raw):
            continue
        if not dest.exists():
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "75", "--resampleWidth", "320",
                            str(raw), "--out", str(dest)], capture_output=True)
        if dest.exists():
            h["img"] = f"img/poster/{fid}.jpg"
            w = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(dest)], capture_output=True, text=True).stdout
            nums = [int(x) for x in re.findall(r"pixel\w+: (\d+)", w)]
            h["ratio"] = round(nums[1] / nums[0], 3) if len(nums) == 2 and nums[0] else None
            if (h["source"] in AUTO or h["source"].startswith("wikipedia-")) and (h["ratio"] or 2) < 1.15:  # wide: not a poster
                dest.unlink()
                out.pop(fid)
                bad.add(fid)
    json.dump(out, open(DATA / "posters.json", "w"), indent=1, ensure_ascii=False, sort_keys=True)
    print(len([h for h in out.values() if h.get("img")]), "posters for", len(films), "films;",
          {s: sum(1 for h in out.values() if h["source"] == s) for s in ("wikipedia", "wikidata", "festival")})


if __name__ == "__main__":
    main()
