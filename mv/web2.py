"""Films of 2021 (MVFF44) and 2022 (MVFF45) from the festival website as archived in the Wayback Machine
-> data/web/2021.json, data/web/2022.json.

    python3 -m mv.web2

2021: the film pages linked from www.mvff.com/program-mvff44/ (capture of 5 Oct 2021).
2022: every www.mvff.com/events/<slug>/ page with a 2022 capture (raw/cdx_mvff.com.txt); events without a
      director or running time (parties, hikes, workshops) are kept as events, not films.
No synopses are taken (they are long festival-written texts); each film links to its archived page.
"""
import html
import json
import re
import time
from pathlib import Path

from .web import RAW, OUT, cached, wb

ROOT = Path(__file__).resolve().parent.parent
NOT_FILMS = re.compile(r"party|hike|workshop|reception|brunch|panel|conversation|masterclass|lunch|scorecard|"
                       r"meet-up|meetup|happy-hour|celebration|awards?-|forum|summit|lab-|industry", re.I)
MONTHS = {"sep": 9, "oct": 10, "nov": 11}


def lines_of(t):
    s = re.sub(r"<script.*?</script>|<style.*?</style>|<svg.*?</svg>", "", t, flags=re.S)
    i = s.find("<main")
    s = s[i:] if i > 0 else s
    s = html.unescape(re.sub(r"<[^>]+>", "\n", s))
    return [l.strip() for l in re.split(r"[ \t]*\n\s*", s) if l.strip()]


def titlecase(t):
    if t.isupper():
        small = {"a", "an", "and", "the", "of", "in", "on", "to", "for", "at", "by", "with", "from", "or", "de", "la", "le", "el"}
        ws = t.lower().split()
        return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(ws))
    return t


def page_title(t):
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    return titlecase(html.unescape(m.group(1)).split(" – ")[0].split(" - Mill")[0].strip()) if m else None


def parse_2022(t, url):
    L = lines_of(t)
    if "Film Info" not in L:
        return None
    k = L.index("Film Info")
    kv, key = {}, None
    for l in L[k + 1:]:
        if l.startswith("Other MVFF") or l == "Explore the program":
            break
        if l.endswith(":") and len(l) < 30:
            key = l[:-1].lower()
            kv[key] = []
        elif key and l != "|":
            kv[key].append(l)
    scr = []
    for i, l in enumerate(L[:k]):
        m = re.search(r"date='(\d{4}-\d\d-\d\d)'", l)
        mm = re.match(r"(\d{1,2}:\d\d [AP]M) — (.+)", L[i + 1]) if i + 1 < len(L) else None
        if m and mm:
            scr.append({"date": m.group(1), "time": mm.group(1), "venue": mm.group(2)})
        elif re.match(r"= index'>(\w{3}) (\d+)", l) and mm:
            mo, d = re.match(r"= index'>(\w{3}) (\d+)", l).groups()
            scr.append({"date": f"2022-{MONTHS.get(mo.lower(), 10):02d}-{int(d):02d}", "time": mm.group(1), "venue": mm.group(2)})
    rt = re.match(r"(\d+)", " ".join(kv.get("running time", [])))
    yr = re.match(r"(\d{4})", " ".join(kv.get("year", [])))
    split = lambda v: [x.strip() for x in ", ".join(v).split(",") if x.strip()]
    dirs = split(kv.get("director", []) or kv.get("directors", []))
    return {"title": page_title(t), "directors": dirs, "countries": split(kv.get("countries", []) or kv.get("country", [])),
            "film_year": int(yr.group(1)) if yr else None, "runtime_min": int(rt.group(1)) if rt else None,
            "cast": split(kv.get("cast", []))[:6], "section": ", ".join(s.title() for s in kv.get("sections", [])) or None,
            "language": ", ".join(kv.get("languages", kv.get("language", []))) or None,
            "screenings": scr, "url": url, "is_short": bool(rt and int(rt.group(1)) < 40)}


HEAD21 = re.compile(r"^(?P<c>[A-Za-z .,/&’'-]+?)\s+(?P<y>(19|20)\d\d),\s*(?P<rt>\d+)\s*min\b(?:\s+Directors?\s+(?P<d>.+))?$")


def parse_2021(t, url):
    L = lines_of(t)
    head = next((i for i, l in enumerate(L[:40]) if HEAD21.match(l)), None)
    if head is None:
        return None
    m = HEAD21.match(L[head])
    dirs = m.group("d") or ""
    if not dirs and head + 1 < len(L) and L[head + 1].lower().startswith("director"):
        dirs = re.sub(r"^directors?\s*", "", L[head + 1], flags=re.I)
    section = L[head - 1] if head >= 1 and L[head - 1].isupper() and "/" in L[head - 1] else None
    scr = []
    for l in L:
        sm = re.match(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*, (Oct|Sep|Nov) (\d+), (\d{1,2}(?::\d\d)?\s*[ap]m), (.+?)(?: \(|$)", l)
        if sm:
            scr.append({"date": f"2021-{MONTHS[sm.group(2).lower()]:02d}-{int(sm.group(3)):02d}",
                        "time": sm.group(4), "venue": sm.group(5).strip()})
    rt = int(m.group("rt"))
    return {"title": page_title(t), "directors": [d.strip() for d in re.split(r",| and |&", dirs) if d.strip()],
            "countries": [c.strip() for c in re.split(r"/|,", m.group("c")) if c.strip()],
            "film_year": int(m.group("y")), "runtime_min": rt, "section": section.title() if section else None,
            "screenings": scr, "url": url, "is_short": rt < 40}


def captures(prefix, year):
    out = {}
    for line in open(RAW / "cdx_mvff.com.txt"):
        k, ts, orig, mt, st = line.split()[:5]
        if st == "200" and k.startswith(prefix):
            out[k] = (ts, orig)
    return out


def main():
    # 2021
    t = cached("prog2021.html", wb("20211005", "https://www.mvff.com/program-mvff44/"))
    skip = {"about-mvff", "active-cinema", "attend", "behind-the-screens", "board-of-directors", "code-of-conduct",
            "contact", "covid", "education", "family", "feed", "hotels", "housing", "tickets", "volunteer", "staff",
            "press-info", "press-releases", "program-mvff44", "mvff-guide-archive", "wp-json", "mind-the-gap"}
    slugs = sorted(set(re.findall(r'href="https?://www\.mvff\.com/([a-z0-9-]+)/?"', t)) - skip)
    films, events = [], []
    for s in slugs:
        if re.search(r"mvff\d|sponsor|photo|gallery|guide|program|award|tribute|spotlight", s):
            continue
        url = f"https://www.mvff.com/{s}/"
        page = cached(f"y2021_{s}.html", wb("20211015", url))
        r = parse_2021(page, url) if page else None
        (films if r else events).append(r or s)
    (OUT / "2021.json").write_text(json.dumps({"year": 2021, "edition": 44, "source": "web", "films": films,
                                               "unparsed": events}, ensure_ascii=False, indent=1))
    print(2021, len(films), "films;", len(events), "other pages", flush=True)
    # 2022
    caps = {k: v for k, v in captures("com,mvff)/events/", 2022).items() if v[0].startswith("2022")}
    films, events = [], []
    for k, (ts, orig) in sorted(caps.items()):
        s = k.split("/events/")[1].strip("/")
        if not s or "?" in s:
            continue
        url = f"https://www.mvff.com/events/{s}/"
        page = cached(f"y2022_{s}.html", wb(ts, url))
        r = parse_2022(page, url) if page else None
        if r and (r["directors"] or r["runtime_min"]) and not NOT_FILMS.search(s):
            films.append(r)
        else:
            events.append(s)
    (OUT / "2022.json").write_text(json.dumps({"year": 2022, "edition": 45, "source": "web", "films": films,
                                               "unparsed": events}, ensure_ascii=False, indent=1))
    print(2022, len(films), "films;", len(events), "events or unparsed", flush=True)


if __name__ == "__main__":
    main()
