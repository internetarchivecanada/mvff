"""Films of the web-era festivals (2023-2026) -> data/web/<year>.json, same film shape as data/programmes.

    python3 -m mv.web

2023-2024: the browse page of www.mvff.com embeds the whole programme as window.FILM_MANIFEST; we read the
           Wayback Machine capture taken during each festival.
2025-2026: app.mvff.com/browse lists the films; each film page (/film/<slug>) is read from the Wayback Machine
           when captured, else live (app.mvff.com has no robots.txt; we wait 5 s between requests anyway).
Downloads are cached in raw/wb/.
"""
import html
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "raw", ROOT / "data" / "web"
S = requests.Session()
S.headers["User-Agent"] = "WaybackLabs-FestivalExplorer/0.1 (Internet Archive research)"
EDITION = {2023: 46, 2024: 47, 2025: 48, 2026: 49}
MANIFEST = {2023: ("20231010", "https://www.mvff.com/browse-program/"),
            2024: ("20241004", "https://www.mvff.com/browse-program/")}
APP_BROWSE = {2025: "20251010", 2026: "20261008"}


def cached(name, url):
    f = RAW / "wb" / name
    if not f.exists() or f.stat().st_size < 500:
        for i in range(5):
            try:
                r = S.get(url, timeout=120)
            except requests.RequestException:
                time.sleep(30 * (i + 1))
                continue
            if r.status_code == 200:
                f.write_bytes(r.content)
                break
            if 400 <= r.status_code < 500 and r.status_code != 429:
                break
            time.sleep(15 * (i + 1))
        time.sleep(2 if "web.archive.org" in url else 5)
    return f.read_text(errors="replace") if f.exists() else ""


def wb(ts, url):
    return f"https://web.archive.org/web/{ts}id_/{url}"


def text(h):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or ""))).strip()


def from_manifest(year):
    ts, url = MANIFEST[year]
    t = cached(f"browse_{year}.html", wb(ts, url))
    i = t.find("window.FILM_MANIFEST")
    d, _ = json.JSONDecoder().raw_decode(t[t.find("=", i) + 1:].lstrip())
    films = []
    for x in d:
        sess = []
        for s in x.get("sessions") or []:
            m = re.match(r"\w+, (\d+ \w+ \d{4}) (\d\d:\d\d)", s.get("startDate", ""))
            if m:
                dt = time.strptime(m.group(1), "%d %b %Y")
                sess.append({"date": time.strftime("%Y-%m-%d", dt), "time": m.group(2), "venue": s.get("venueName")})
        films.append({
            "title": html.unescape(x["title"]), "original_title": x.get("originalTitle"),
            "directors": [d["name"] for d in x.get("director") or []],
            "countries": x.get("country") or [], "film_year": x.get("year"), "runtime_min": x.get("runtime"),
            "language": x.get("language"), "section": ", ".join(x.get("section") or []) or None,
            "sections": x.get("section") or [], "strand": x.get("strand"), "initiative": x.get("initiative"),
            "slot": None, "premiere": x.get("premiere"), "is_short": (x.get("type") or "").lower().startswith("short"),
            "type": x.get("type"), "shorts_program": None,
            "guests": [g[0] if isinstance(g, list) else g for g in (x.get("guests") or [])],
            "screenings": sess, "logline": text(x.get("abstract"))[:400],
            "url": x.get("url"), "slug": x.get("slug"), "child_ids": x.get("childIDs") or [], "id": x.get("ID"),
        })
    # programmes of shorts list their films as children
    by_id = {f["id"]: f for f in films}
    for f in films:
        for c in f["child_ids"]:
            if c in by_id and by_id[c] is not f:
                by_id[c]["shorts_program"] = f["title"]
    return films


LABELS = ["COUNTRY", "YEAR", "Premiere", "RUNTIME", "DIRECTOR/S", "PRODUCER", "WRITER", "CINEMATOGRAPHER", "EDITOR",
          "FORMAT", "LANGUAGE", "CAST", "MUSIC", "SUBTITLES"]


def parse_app_film(t, slug):
    s = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", t, flags=re.S)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", "\n", s))
    lines = [re.sub(r"\s+", " ", l).strip() for l in s.split("\n")]
    lines = [l for l in lines if l]
    title = None
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    if m and text(m.group(1)):
        title = text(m.group(1)).split(" | ")[0].split(" - ")[0].strip() or None
    try:
        k = lines.index("Director/s")
    except ValueError:
        return None
    # the film block reads: title, "US •", "2025 •", "12 mins", logline (may be split by inline tags), "Director/s"
    rt = next((i for i in range(k - 1, max(0, k - 12), -1) if re.match(r"^\d+ mins?( •)?$", lines[i])), None)
    tail = [l for l in lines[rt + 1:k] if not (l.isupper() and "PREMIER" in l)] if rt is not None else []
    logline = " ".join(tail).replace(" ’", "’").strip() or None
    first = rt
    while first is not None and first > 0 and re.search(r"•$", lines[first - 1]):
        first -= 1
    if first and first > 0:
        title = lines[first - 1]
    logline = logline if logline and len(logline) > 25 else None
    rec = {"title": title, "logline": logline, "guests": [], "programs": []}
    j = k + 1
    while j < len(lines) and lines[j] not in ("Expected Guests", "THIS FILM IS INCLUDED IN:", "✕"):
        j += 1
    if j < len(lines) and lines[j] == "Expected Guests":
        j += 1
        while j < len(lines) and ":" in lines[j] and lines[j] != "THIS FILM IS INCLUDED IN:":
            n, _, role = lines[j].partition(":")
            rec["guests"].append({"name": n.strip().title(), "role": role.strip()})
            j += 1
    if j < len(lines) and lines[j] == "THIS FILM IS INCLUDED IN:":
        j += 1
        while j < len(lines) and lines[j] not in ("✕", "Venue Name"):
            rec["programs"].append(lines[j])
            j += 1
    kv = {}
    for i, l in enumerate(lines):
        if l in LABELS and i + 1 < len(lines) and l not in kv:
            kv[l] = lines[i + 1]
    rm = re.match(r"(\d+)", kv.get("RUNTIME", ""))
    rec.update({
        "countries": [c.strip() for c in kv.get("COUNTRY", "").split(",") if c.strip()],
        "film_year": int(kv["YEAR"]) if kv.get("YEAR", "").isdigit() else None,
        "runtime_min": int(rm.group(1)) if rm else None,
        "premiere": kv.get("Premiere", "").title() or None,
        "directors": [d.strip() for d in re.split(r",| and ", kv.get("DIRECTOR/S", "")) if d.strip()],
        "language": kv.get("LANGUAGE"),
        "producers": kv.get("PRODUCER"), "writers": kv.get("WRITER"),
        "cast": [c.strip() for c in kv.get("CAST", "").split(",") if c.strip()][:6],
        "edition_seen": (re.findall(r"MVFF(\d\d)", t) or [None])[0],
    })
    return rec


def from_app(year):
    t = cached(f"app_browse_{year}.html", wb(APP_BROWSE[year], "https://app.mvff.com/browse"))
    slugs = sorted(set(re.findall(r'href="(?:https://app\.mvff\.com)?/film/([a-z0-9-]+)"', t))
                   | set(re.findall(r"/drive_serve/([a-z0-9-]+)/0-600", t)))
    caps = {}
    for line in open(RAW / "cdx_mvff.com.txt"):
        k, ts, orig, mt, st = line.split()[:5]
        if k.startswith("com,mvff,app)/film/") and st == "200":
            caps[k.split("/film/")[1]] = ts
    films = []
    for slug in slugs:
        url = f"https://app.mvff.com/film/{slug}"
        src = wb(caps[slug], url) if slug in caps else url
        page = cached(f"app_{year}_{slug}.html", src)
        rec = parse_app_film(page, slug) if page else None
        if not rec:
            films.append({"title": slug.replace("-", " ").title(), "slug": slug, "url": url, "parse_failed": True})
            continue
        if not rec.get("title"):     # spotlight and tribute pages open with an introduction, not the film block
            small = {"a", "an", "and", "the", "of", "in", "on", "to", "for", "at", "by", "with", "from", "or"}
            ws = slug.split("-")
            rec["title"] = " ".join(w if (i and w in small) else w.capitalize() for i, w in enumerate(ws))
        programs = [p for p in rec.pop("programs") if p]
        films.append({**rec, "slug": slug, "url": url, "source": "wayback" if slug in caps else "live",
                      "is_short": bool(rec.get("runtime_min") and rec["runtime_min"] < 40),
                      "shorts_program": next((p for p in programs if p.lower().startswith("shorts")), None),
                      "programs": programs, "screenings": [], "section": None, "slot": None,
                      "original_title": None})
    return films


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (RAW / "wb").mkdir(exist_ok=True)
    for year in (2023, 2024, 2025, 2026):
        films = from_manifest(year) if year in MANIFEST else from_app(year)
        out = {"year": year, "edition": EDITION[year], "source": "web", "films": films}
        (OUT / f"{year}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(year, len(films), "films;", sum(1 for f in films if f.get("is_short")), "shorts;",
              sum(1 for f in films if f.get("parse_failed")), "parse failures", flush=True)


if __name__ == "__main__":
    main()
