"""data/programmes/*.json (printed programmes) + data/web/*.json (festival websites) + raw/issuu_map.tsv
-> data/festival.json: editions 1978-2026, films, people, venues, sections, countries.

    python3 -m mv.model
"""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, RAW = ROOT / "data", ROOT / "raw"
FIRST = 1978
LAST = 2026

# Wayback Machine copies of the printed programmes the film lists come from (raw/pdf; see README)
PROGRAMME_PDF = {
    2001: ("20050506134948", "http://cafilm.org:80/pdf/2001%20MVFF%20Schedule.pdf", "Festival schedule"),
    2002: ("20040411103537", "http://www.cafilm.org:80/2002%20schedule%20pdfs/2002%20Film%20Notes.alphafinal.pdf", "Film notes"),
    2003: ("20040203222415", "http://www.cafilm.org:80/MVFF2003Schedule.pdf", "Festival schedule"),
    2004: ("20060506053905", "http://www.cafilm.org:80/MVFF2004Schedule.pdf", "Festival programme"),
    2005: ("20061117035515", "http://mvff.com/2005/files/pdfs/2005FilmSched.pdf", "Festival programme"),
    2006: ("20061117035426", "http://mvff.com/files/pdfs/MVFF2006SP.pdf", "Souvenir programme"),
    2007: ("20100707020613", "http://www.cafilm.org/mvff/MVFF2007-SouvenirProgramGuide.pdf", "Souvenir programme guide"),
    2008: ("20100707020647", "http://www.cafilm.org/mvff/MVFF2008_SouvenirProgramGuide_NoAds-lo.pdf", "Souvenir programme guide"),
    2009: ("20100707020525", "http://www.cafilm.org/mvff/MVFF2009_SouvenirProgramGuide.pdf", "Souvenir programme guide"),
    2010: ("20101103090555", "http://mvff.com/documents/2010MVFF-Schedule.pdf", "Festival programme"),
    2011: ("20111005062749", "http://www.cafilm.org/2011mvff/2011MVFF_FilmSchedule.pdf", "Film schedule"),
    2024: ("20240913103016", "https://www.mvff.com/wp-content/uploads/2024/09/Schedule_MVFF47.pdf", "Schedule"),
    2025: ("20250918155533", "https://www.mvff.com/wp-content/uploads/2025/09/MVFF48_Sched_v3.pdf", "Schedule"),
    2026: ("20261016054521", "https://www.mvff.com/wp-content/uploads/2026/09/MVFF49_Schedule_digital.pdf", "Schedule"),
}
WEB_SOURCE = {
    2023: ("20231010", "https://www.mvff.com/browse-program/", "Festival website programme (MVFF46)"),
    2024: ("20241004", "https://www.mvff.com/browse-program/", "Festival website programme (MVFF47)"),
    2025: ("20251010", "https://app.mvff.com/browse", "Festival website programme (MVFF48)"),
    2026: ("20261008", "https://app.mvff.com/browse", "Festival website programme (MVFF49)"),
}
COUNTRY = {"us": "USA", "u.s.": "USA", "u.s.a.": "USA", "usa": "USA", "united states": "USA",
           "united states of america": "USA", "uk": "UK", "u.k.": "UK", "united kingdom": "UK", "england": "UK",
           "great britain": "UK", "scotland": "UK", "wales": "UK", "northern ireland": "UK",
           "w. germany": "West Germany", "west germany": "West Germany", "ussr": "USSR", "korea": "South Korea",
           "s. korea": "South Korea", "republic of korea": "South Korea", "holland": "Netherlands",
           "the netherlands": "Netherlands", "czech republic": "Czechia", "czech rep.": "Czechia",
           "hong kong": "Hong Kong", "uae": "United Arab Emirates", "drc": "DR Congo"}


def txt(v):
    """A display string from a value that may be a list (web data) or a string (programmes)."""
    if isinstance(v, list):
        v = ", ".join(str(x) for x in v if x)
    v = (str(v).strip() or None) if v is not None else None
    return re.sub(r"\bUs\b", "US", v) if v else v


VENUES = [  # (pattern, canonical venue) for the screen-level names the programmes and sites use
    (r"rafael|1312 mission|mark fishkin room", "Smith Rafael Film Center, San Rafael"),
    (r"sequoia", "Sequoia Theatre, Mill Valley"),
    (r"142 throckmorton|throckmorton", "142 Throckmorton Theatre, Mill Valley"),
    (r"^cinema$|century cinema|pacific cinema", "Century Cinema, Corte Madera"),
    (r"regency", "Regency Theatre, San Rafael"),
    (r"castro", "Castro Theatre, San Francisco"),
    (r"lark", "Lark Theater, Larkspur"),
    (r"bampfa", "BAMPFA, Berkeley"),
    (r"outdoor art club", "Outdoor Art Club, Mill Valley"),
    (r"sweetwater", "Sweetwater Music Hall, Mill Valley"),
    (r"roxie", "Roxie Theater, San Francisco"),
    (r"streaming", "CAFILM Streaming (online)"),
    (r"larkspur landing", "Cinemark Larkspur Landing"),
    (r"embarcadero", "Embarcadero Center Cinema, San Francisco"),
]


def venue(v):
    for pat, name in VENUES:
        if re.search(pat, v or "", re.I):
            return name
    return (v or "").strip() or None


def slugify(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80] or "x"


def country(c):
    c = re.sub(r"\s+", " ", (c or "").strip().strip("."))
    if not c:
        return None
    return COUNTRY.get(c.lower(), c if not c.isupper() or len(c) <= 3 else c.title())


def split_countries(cs):
    out = []
    for c in cs or []:
        for p in re.split(r"/|,| and |;", c):
            p = country(p)
            if p and p not in out:
                out.append(p)
    return out


def norm_name(n):
    n = re.sub(r"\s+", " ", (n or "").strip().strip(",;"))
    if n.isupper() and len(n) > 3:
        n = " ".join(w.capitalize() if not re.match(r"^(Mc|Mac)", w.capitalize()) else w.capitalize()
                     for w in n.lower().split())
    return n


def load_guides():
    """edition number -> list of guide documents shown on mvff.com's programme guide archive."""
    out = defaultdict(list)
    f = RAW / "issuu_map.tsv"
    if not f.exists():
        return out
    for line in f.read_text().splitlines():
        slug, _, rest = line.partition("\t")
        m = re.search(r"mv[vf]f-?(\d\d)", slug) or re.search(r"mvf(\d\d)", slug)
        if not m:
            continue
        ed = int(m.group(1))
        for tok in rest.split():
            if tok.startswith("wp-content"):
                out[ed].append({"kind": "pdf", "url": "https://www.mvff.com/" + tok, "page": f"https://www.mvff.com/{slug}/"})
            else:
                out[ed].append({"kind": "issuu", "id": tok, "url": f"https://issuu.com/smithrafaelfilmcenter/docs/{tok}",
                                "page": f"https://www.mvff.com/{slug}/"})
    return out


def main():
    guides = load_guides()
    E, F, P, V = {}, {}, {}, defaultdict(lambda: {"years": set(), "screenings": 0})
    sections = defaultdict(lambda: defaultdict(list))
    person_roles = defaultdict(lambda: defaultdict(set))   # pid -> year -> roles
    person_films = defaultdict(set)

    def person(name):
        name = norm_name(name)
        if not name or len(name) < 3 or not re.search(r"[A-Za-z]", name):
            return None
        pid = slugify(name)
        P.setdefault(pid, {"id": pid, "name": name})
        return pid

    for y in range(FIRST, LAST + 1):
        E[y] = {"year": y, "edition": y - FIRST + 1, "dates": None, "films": [], "events": [], "awards": [],
                "staff": [], "venues": [], "guides": guides.get(y - FIRST + 1, []), "sources": [], "notes": None}
        if y in PROGRAMME_PDF:
            ts, url, label = PROGRAMME_PDF[y]
            E[y]["sources"].append({"label": label, "kind": "pdf", "url": url,
                                    "wayback": f"https://web.archive.org/web/{ts}/{url}"})
        if y in WEB_SOURCE:
            ts, url, label = WEB_SOURCE[y]
            E[y]["sources"].append({"label": label, "kind": "web", "url": url,
                                    "wayback": f"https://web.archive.org/web/{ts}/{url}"})

    def add_films(y, films, origin):
        seen = set()
        for f in films:
            title = re.sub(r"\s+", " ", (f.get("title") or "").strip())
            if not title or f.get("parse_failed"):      # web pages we could not read (mostly shorts programmes)
                continue
            fid = f"{y}-{slugify(title)}"
            if fid in seen:
                fid += "-2"
            seen.add(fid)
            if fid in F:      # a printed programme wins over the web record for the same year
                continue
            dirs = [d for d in (person(x) for x in f.get("directors") or []) if d]
            guests = []
            for g in f.get("guests") or []:
                gname = g.get("name") if isinstance(g, dict) else g
                gid = person(gname)
                if gid:
                    guests.append({"id": gid, "role": (g.get("role") if isinstance(g, dict) else None)})
            cast = [c for c in (person(x) for x in f.get("cast") or []) if c]
            rec = {
                "id": fid, "year": y, "title": title, "original_title": txt(f.get("original_title")),
                "directors": dirs, "countries": split_countries(f.get("countries")),
                "film_year": f.get("film_year") if isinstance(f.get("film_year"), int) else None,
                "runtime": f.get("runtime_min") if isinstance(f.get("runtime_min"), int) else None,
                "language": txt(f.get("language")),
                "section": txt(f.get("section")), "slot": txt(f.get("slot")), "premiere": txt(f.get("premiere")),
                "is_short": bool(f.get("is_short")) or (origin == "web" and isinstance(f.get("runtime_min"), int)
                                                          and f["runtime_min"] < 40), "shorts_program": txt(f.get("shorts_program")),
                "guests": guests, "cast": cast,
                "screenings": [s for s in f.get("screenings") or [] if isinstance(s, dict)],
                "summary": f.get("summary") or f.get("logline"),
                "summary_kind": "summary" if f.get("summary") else ("logline" if f.get("logline") else None),
                "page": f.get("page"), "origin": origin,
                "web_url": f.get("url") if origin == "web" else None,
            }
            F[fid] = rec
            E[y]["films"].append(fid)
            for d in dirs:
                person_roles[d][y].add("director")
                person_films[d].add(fid)
            for g in guests:
                person_roles[g["id"]][y].add("guest")
                person_films[g["id"]].add(fid)
            for c in cast:
                person_roles[c][y].add("cast")
                person_films[c].add(fid)
            for s in rec["screenings"]:
                if s.get("venue"):
                    vk = venue(s["venue"])
                    V[vk]["years"].add(y)
                    V[vk]["screenings"] += 1
            if rec["section"]:
                for sec in re.split(r",\s*", rec["section"]):
                    sections[sec.strip()][y].append(fid)

    for f in sorted((DATA / "programmes").glob("*.json")):
        d = json.loads(f.read_text())
        y = d["year"]
        E[y].update({"dates": d.get("dates"), "notes": d.get("notes"),
                     "venues": d.get("venues") or [], "sections": d.get("sections") or []})
        add_films(y, d.get("films") or [], "programme")
        for i, ev in enumerate(d.get("events") or []):
            eid = f"{y}-e{i + 1}-{slugify(ev.get('title'))[:40]}"
            people = []
            for p in ev.get("people") or []:
                pid = person(p.get("name"))
                if pid:
                    people.append({"id": pid, "role": p.get("role")})
                    person_roles[pid][y].add(p.get("role") or "event")
            E[y]["events"].append({**{k: ev.get(k) for k in ("title", "kind", "date", "time", "venue", "summary",
                                                             "related_films", "page")},
                                   "id": eid, "people": people})
        for a in d.get("awards") or []:
            E[y]["awards"].append(a)
            pid = person(a.get("recipient"))
            if pid:
                person_roles[pid][y].add("honoree")
        for s in d.get("staff") or []:
            pid = person(s.get("name"))
            if pid:
                E[y]["staff"].append({"id": pid, "role": s.get("role")})
                person_roles[pid][y].add("staff")
    WEB_NOTE = {
        2021: "Films with a page on www.mvff.com that the Wayback Machine captured during the 2021 festival and that "
              "we could read automatically; a few pages in other layouts, and the shorts programmes, are missing.",
        2022: "Only films whose pages on www.mvff.com were captured by the Wayback Machine in 2022; the full "
              "programme was larger.",
        2023: "The full programme as published on www.mvff.com (captured 10 October 2023).",
        2024: "The full programme as published on www.mvff.com (captured 4 October 2024).",
        2025: "The programme listed in the festival app (captured 10 October 2025).",
        2026: "The programme listed in the festival app (captured 8 October 2026).",
    }
    for f in sorted((DATA / "web").glob("*.json")):
        d = json.loads(f.read_text())
        add_films(d["year"], d.get("films") or [], "web")
        E[d["year"]]["notes"] = E[d["year"]]["notes"] or WEB_NOTE.get(d["year"])

    for pid, p in P.items():
        yrs = person_roles.get(pid, {})
        p["years"] = sorted(yrs)
        p["roles"] = {str(y): sorted(r) for y, r in sorted(yrs.items())}
        p["films"] = sorted(person_films.get(pid, []))
    P = {k: v for k, v in P.items() if v["years"]}
    out = {"editions": {str(y): e for y, e in E.items()}, "films": F, "people": P,
           "venues": {k: {"name": k, "years": sorted(v["years"]), "screenings": v["screenings"]} for k, v in V.items()},
           "sections": {k: {str(y): ids for y, ids in v.items()} for k, v in sections.items()}}
    (DATA / "festival.json").write_text(json.dumps(out, ensure_ascii=False))
    n_years = sum(1 for e in E.values() if e["films"])
    print(f"{len(F)} films in {n_years} editions; {len(P)} people; {len(V)} venues; {len(sections)} sections")
    for y, e in E.items():
        if e["films"] or e["guides"]:
            print(y, e["edition"], len(e["films"]), "films", len(e["events"]), "events", len(e["guides"]), "guides")


if __name__ == "__main__":
    main()
