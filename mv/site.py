"""Build the static site into public/ from data/festival.json and data/inventory.json.

    python3 -m mv.site
"""
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, PUBLIC = ROOT / "data", ROOT / "public"
STATIC = Path(__file__).resolve().parent / "static"
TITLE = "Mill Valley Film Festival Explorer"
BASE_URL = "https://wayback-labs.sf.archive.org/mvff/"
V = "2"
BUILT = "18 November 2026"
NAV = [("index.html", "Years"), ("films.html", "Films"), ("programmes.html", "Programmes"), ("posters.html", "Posters"), ("people.html", "People"), ("honorees.html", "Tributes"),
       ("countries.html", "Countries"), ("archive.html", "What's archived"), ("search.html", "Search"),
       ("about.html", "About")]
LOGO = ('<svg width="34" height="34" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="15" '
        'fill="#b8862b"/><path d="M5 23 L12 12 L16 18 L20 9 L27 23 Z" fill="#16201c"/><circle cx="23" cy="8" r="2.4" '
        'fill="#16201c"/></svg>')


def plural(n, w, ws=None):
    return f"{n:,} {w if n == 1 else (ws or w + 's')}"


def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def nice_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d")
    except Exception:
        return d or ""


def wb_link(url, ts="2026"):
    return f"https://web.archive.org/web/{ts}/{url}"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "x"


class Site:
    def __init__(self):
        d = json.load(open(DATA / "festival.json"))
        self.E = {int(k): v for k, v in d["editions"].items()}
        self.F, self.P, self.V, self.SEC = d["films"], d["people"], d["venues"], d["sections"]
        inv = DATA / "inventory.json"
        self.inv = json.load(open(inv)) if inv.exists() else []
        sv = DATA / "saved.json"
        self.saved = json.load(open(sv)) if sv.exists() else {}
        po = DATA / "posters.json"
        self.posters = {k: v for k, v in (json.load(open(po)) if po.exists() else {}).items()
                        if v.get("img") and k in self.F and (ROOT / "assets" / v["img"]).exists()}
        self.urls = []
        self.country_films = defaultdict(list)
        for f in self.F.values():
            for c in f["countries"]:
                self.country_films[c].append(f["id"])
        self.years = sorted(self.E)
        self.film_years = [y for y in self.years if self.E[y]["films"]]

    # ---------- page frame ----------
    def page(self, path, title, body, here=None, desc=None, depth=None):
        depth = path.count("/") if depth is None else depth
        up = "../" * depth
        nav = "".join(f'<a href="{up}{h}"{" aria-current=page" if here == h else ""}>{t}</a>' for h, t in NAV)
        full = f"{title} · {TITLE}" if title != TITLE else TITLE
        html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(full)}</title>
<meta name="description" content="{escape(desc or 'Films, people and programmes of the Mill Valley Film Festival, 1978 to 2026, and what the Wayback Machine holds of them.')}">
<link rel="stylesheet" href="{up}style.css?v={V}"><link rel="icon" href="{up}favicon.svg" type="image/svg+xml">
<link rel="canonical" href="{BASE_URL}{path}">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap"><a class="brand" href="{up}index.html">{LOGO}<span class="bt">Mill Valley Film Festival<em>Explorer · 1978–2026</em></span></a>
<nav class="main" aria-label="Main">{nav}</nav></div></header>
<main id="main" class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
<p>A Wayback Machine Labs experiment, Internet Archive. Made by Claude (Anthropic) at the direction of Mark Graham.
Not affiliated with the Mill Valley Film Festival or the California Film Institute. Feedback? <a href="mailto:info@archive.org">Email us</a>.</p>
<p>Film lists come from the festival's printed programmes and websites as saved in the
<a href="https://web.archive.org/">Wayback Machine</a>. <a href="{up}about.html">About this site</a> ·
<a href="{up}about.html#accessibility">Accessibility</a></p>
</div></footer>
<script src="{up}app.js?v={V}" defer></script>
</body></html>"""
        out = PUBLIC / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        self.urls.append(path)

    def flink(self, fid, up="../", year=False):
        f = self.F[fid]
        t = escape(f["title"])
        return f'<a href="{up}films/{fid}.html">{t}</a>' + (f' <span class="count">{f["year"]}</span>' if year else "")

    def plink(self, pid, up="../"):
        return f'<a href="{up}people/{pid}.html">{escape(self.P[pid]["name"])}</a>' if pid in self.P else ""

    def film_meta(self, f, up="../"):
        bits = []
        if f["directors"]:
            bits.append(", ".join(escape(self.P[d]["name"]) for d in f["directors"] if d in self.P))
        if f["countries"]:
            bits.append(" / ".join(escape(c) for c in f["countries"]))
        if f["film_year"]:
            bits.append(str(f["film_year"]))
        if f["runtime"]:
            bits.append(f'{f["runtime"]} min')
        return " · ".join(b for b in bits if b)

    def film_li(self, fid, up="../", year=False):
        f = self.F[fid]
        n = " ".join([f["title"], self.film_meta(f), f.get("section") or ""])
        return (f'<li data-n="{escape(n)}" data-short="{"1" if f["is_short"] else "0"}" data-y="{f["year"]}">'
                f'<span class="t">{self.flink(fid, up, year)}</span>'
                f'<span class="m">{self.film_meta(f, up)}</span></li>')

    def poster(self, fid, up="../", cls="poster"):
        po = self.posters.get(fid)
        if not po:
            return ""
        return (f'<img class="{cls}" src="{up}{po["img"]}" alt="Poster for {escape(self.F[fid]["title"])}" loading="lazy" '
                f'width="320" height="{int(320 * (po.get("ratio") or 1.48))}">')

    def poster_credit(self, fid):
        po = self.posters.get(fid)
        if not po:
            return ""
        lab = {"wikipedia": "Wikipedia", "wikidata": "Wikimedia Commons"}.get(po["source"]) or escape(po.get("credit") or "the web")
        return f'Poster from <a href="{escape(po.get("page") or po["src"])}">{lab}</a>'

    def strip(self, ids, up="../", n=12):
        ids = [i for i in ids if i in self.posters][:n]
        if not ids:
            return ""
        return '<div class="pstrip">' + "".join(f'<a href="{up}films/{i}.html" title="{escape(self.F[i]["title"])}">{self.poster(i, up)}</a>' for i in ids) + "</div>"

    def guide_links(self, e):
        out = []
        for g in e["guides"]:
            if g["kind"] == "issuu":
                out.append(f'<a href="{escape(g["page"])}">Programme guide on mvff.com</a> '
                           f'(<a href="{escape(g["url"])}">Issuu</a>, <a href="{wb_link(g["url"])}">Wayback Machine copy</a>)')
            else:
                out.append(f'<a href="{escape(g["url"])}">Programme guide (PDF)</a> '
                           f'(<a href="{wb_link(g["url"])}">Wayback Machine copy</a>)')
        return out

    # ---------- pages ----------
    def build(self):
        if PUBLIC.exists():
            shutil.rmtree(PUBLIC)
        PUBLIC.mkdir()
        for f in STATIC.iterdir():
            shutil.copy(f, PUBLIC / f.name)
        for sub in ("img", "pagefind"):
            if (ROOT / "assets" / sub).exists():
                shutil.copytree(ROOT / "assets" / sub, PUBLIC / sub)
        self.index()
        for y in self.years:
            self.year_page(y)
        for fid in self.F:
            self.film_page(fid)
        for pid in self.P:
            self.person_page(pid)
        self.films_index()
        self.posters_page()
        self.people_index()
        self.honorees()
        self.countries()
        self.venues()
        self.archive()
        self.programmes()
        self.about()
        self.search()
        self.misc()

    def index(self):
        nf = len(self.F)
        ny = len(self.film_years)
        cards = []
        for y in self.years:
            e = self.E[y]
            n = len(e["films"])
            ct = plural(n, "film") if n else ("programme guide" if e["guides"] else "no programme found yet")
            cls = "ed" if n else "ed guide"
            cards.append(f'<li class="{cls}"><a href="years/{y}.html"><span class="yr">{y}</span>'
                         f'<span class="ord">{ordinal(e["edition"])} festival</span><span class="ct">{ct}</span></a></li>')
        honorees = sum(1 for p in self.P.values() if any("honoree" in r for r in p["roles"].values()))
        body = f"""<div class="hero"><h1>Mill Valley Film Festival Explorer</h1>
<p class="lede">Forty-nine years of the Mill Valley Film Festival in Marin County, California, from its first
weekend at the Sequoia Theatre in 1978 to 2026: the films, the filmmakers who came, the tributes, and the
programme guides that recorded them, with what the Wayback Machine has saved of it all.</p>
<form class="bigsearch" action="search.html" role="search"><label for="hq" class="vh hide">Search</label>
<input id="hq" name="q" placeholder="Search films, directors, guests, countries…" aria-label="Search films and people">
<button>Search</button></form>
<p class="stats"><a href="films.html"><b>{nf:,}</b>films</a> <a href="people.html"><b>{len(self.P):,}</b>people</a>
<a href="countries.html"><b>{len(self.country_films)}</b>countries</a> <a href="honorees.html"><b>{honorees}</b>honorees</a>
<a href="archive.html"><b>{len(self.years)}</b>editions</a> <a href="venues.html"><b>{len(self.V)}</b>venues</a></p></div>
<section><h2>Poster wall</h2><p class="note">{len(self.posters):,} film posters, from Wikipedia, Wikimedia Commons and the films' own sites and distributors. <a href="posters.html">See them all →</a></p>
{self.strip(sorted(self.posters, key=lambda i: (-self.F[i]["year"], self.F[i]["title"])), "", 12)}</section>
<h2>The festivals</h2>
<p class="legend">Solid cards have a film list read from that year's programme or website ({ny} so far). Dashed
cards link to the festival's own scan of that year's programme guide; their films are not yet in this explorer.</p>
<ul class="eds">{''.join(cards)}</ul>"""
        self.page("index.html", TITLE, body, "index.html", depth=0)

    def year_page(self, y):
        e = self.E[y]
        films = e["films"]
        feats = [f for f in films if not self.F[f]["is_short"]]
        shorts = [f for f in films if self.F[f]["is_short"]]
        prev = f'<a href="{y - 1}.html">← {y - 1}</a>' if y - 1 in self.E else ""
        nxt = f'<a href="{y + 1}.html">{y + 1} →</a>' if y + 1 in self.E else ""
        facts = [("Edition", f'{ordinal(e["edition"])} Mill Valley Film Festival')]
        if e.get("dates"):
            facts.append(("Dates", escape(e["dates"])))
        if films:
            facts.append(("Films", f"{len(feats)} features and longer works, {len(shorts)} shorts"))
        src = []
        for s in e["sources"]:
            src.append(f'{escape(s["label"])}: <a href="{escape(s["wayback"])}">Wayback Machine copy</a>')
        gl = self.guide_links(e)
        body = [f'<p class="crumbs"><a href="../index.html">All years</a> · {prev} {nxt}</p>',
                f'<h1>{y}: the {ordinal(e["edition"])} festival</h1>',
                '<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl>"]
        if gl or src:
            body.append('<div class="card"><h3 style="margin-top:0">Sources</h3><ul class="plain">'
                        + "".join(f"<li>{x}</li>" for x in gl + src) + "</ul></div>")
        if not films:
            body.append('<p class="callout">This year\'s films have not been read into the explorer yet. '
                        + ("The festival has put a scan of the programme guide online (linked above)." if gl else
                           "We have not found a programme for this year online yet.") + "</p>")
        else:
            secs = Counter(self.F[f].get("section") for f in films if self.F[f].get("section"))
            body.append(f'<h2>Films <span class="count">{len(films)}</span></h2>')
            body.append(self.strip(sorted(films, key=lambda i: (self.F[i]["is_short"], self.F[i]["title"])), "../", 14))
            body.append('<div class="filter" data-target="ul.films li"><input type="search" placeholder="Filter this year\'s films" '
                        'aria-label="Filter films"><span class="shown"></span>'
                        '<div class="chips"><button class="chip" data-k="short" data-v="0" aria-pressed="false">Features</button>'
                        '<button class="chip" data-k="short" data-v="1" aria-pressed="false">Shorts</button></div></div>')
            body.append('<ul class="films">' + "".join(self.film_li(f) for f in sorted(films, key=lambda i: self.F[i]["title"].lower().lstrip("'\"¡¿").removeprefix("the "))) + "</ul>")
            if secs:
                body.append('<h3>Sections</h3><p>' + " ".join(f'<span class="tag">{escape(s)} ({n})</span>' for s, n in secs.most_common()) + "</p>")
        if e["events"]:
            body.append(f'<h2>Tributes, talks and events <span class="count">{len(e["events"])}</span></h2><ul class="plain">')
            for ev in sorted(e["events"], key=lambda v: (v.get("date") or "9", v.get("time") or "")):
                ppl = ", ".join(self.plink(p["id"]) for p in ev["people"] if p["id"] in self.P)
                when = " · ".join(x for x in (nice_date(ev.get("date")), ev.get("time"), ev.get("venue")) if x)
                body.append(f'<li class="card"><b>{escape(ev.get("title") or "")}</b> <span class="tag">{escape(ev.get("kind") or "event")}</span>'
                            + (f'<span class="sub">{escape(when)}</span>' if when else "")
                            + (f'<p style="margin:.4em 0">{escape(ev["summary"])}</p>' if ev.get("summary") else "")
                            + (f'<span class="sub">With {ppl}</span>' if ppl else "") + "</li>")
            body.append("</ul>")
        if e["awards"]:
            body.append('<h2>Awards</h2><ul class="plain">' + "".join(
                f'<li>{escape(a.get("name") or "Award")}: {escape(a.get("recipient") or "")}'
                + (f' (<cite>{escape(a["film"])}</cite>)' if a.get("film") else "") + "</li>" for a in e["awards"]) + "</ul>")
        if e["staff"]:
            body.append(f'<details><summary>Festival staff and programme writers named in the programme ({len(e["staff"])})</summary>'
                        '<ul class="cols">' + "".join(f'<li>{self.plink(s["id"])} <span class="sub">{escape(s.get("role") or "")}</span></li>'
                                                     for s in e["staff"] if s["id"] in self.P) + "</ul></details>")
        if e.get("notes") and len(e["notes"]) < 400:
            body.insert(4, f'<p class="callout">{escape(e["notes"])}</p>')
        elif e.get("notes"):
            body.append(f'<details><summary>Reading notes for this year\'s programme</summary><p class="note">{escape(e["notes"])}</p></details>')
        self.page(f"years/{y}.html", f"{y} ({ordinal(e['edition'])} festival)", "".join(body), "index.html",
                  desc=f"Films and events of the {ordinal(e['edition'])} Mill Valley Film Festival, {y}.")

    def film_page(self, fid):
        f = self.F[fid]
        e = self.E[f["year"]]
        facts = []
        if f["directors"]:
            facts.append(("Directed by", ", ".join(self.plink(d) for d in f["directors"])))
        if f.get("original_title"):
            facts.append(("Original title", escape(f["original_title"])))
        if f["countries"]:
            facts.append(("Country", " / ".join(f'<a href="../countries.html#{slug(c)}">{escape(c)}</a>' for c in f["countries"])))
        if f["film_year"]:
            facts.append(("Year", str(f["film_year"])))
        if f["runtime"]:
            facts.append(("Running time", f'{f["runtime"]} minutes'))
        if f.get("language"):
            facts.append(("Language", escape(f["language"])))
        if f.get("section"):
            facts.append(("Festival section", escape(f["section"])))
        if f.get("slot"):
            facts.append(("Slot", escape(f["slot"])))
        if f.get("premiere"):
            facts.append(("Premiere", escape(f["premiere"])))
        if f.get("shorts_program"):
            facts.append(("Screened in", escape(f["shorts_program"])))
        if f["cast"]:
            facts.append(("With", ", ".join(self.plink(c) for c in f["cast"])))
        if f["guests"]:
            facts.append(("Guests", ", ".join(self.plink(g["id"]) + (f' <span class="count">{escape(g["role"])}</span>' if g.get("role") else "")
                                               for g in f["guests"] if g["id"] in self.P)))
        scr = [", ".join(x for x in (nice_date(s.get("date")), s.get("time"), s.get("venue")) if x) for s in f["screenings"]]
        if scr:
            facts.append(("Screenings", "<br>".join(escape(s) for s in scr if s)))
        src = []
        for s in e["sources"]:
            if (f["origin"] == "programme" and s["kind"] == "pdf") or (f["origin"] == "web" and s["kind"] == "web"):
                page = f' (page {f["page"]} of the PDF)' if f.get("page") and s["kind"] == "pdf" else ""
                src.append(f'{escape(s["label"])}{page}: <a href="{escape(s["wayback"])}">Wayback Machine copy</a>')
        if f.get("web_url"):
            src.append(f'Festival film page: <a href="{wb_link(f["web_url"])}">Wayback Machine copy</a>')
        other = [o for o in self.F.values() if o["id"] != fid and o["title"].lower() == f["title"].lower()]
        summary = ""
        if f.get("summary"):
            label = "In brief" if f.get("summary_kind") == "summary" else "From the festival"
            summary = f'<h3>{label}</h3><p class="lede">{escape(f["summary"])}</p>'
        if fid in self.posters:
            src.append(self.poster_credit(fid))
        po = self.poster(fid, "../", "poster big")
        body = (f'<p class="crumbs"><a href="../years/{f["year"]}.html">{f["year"]} ({ordinal(e["edition"])} festival)</a></p>'
                f'<div class="fhead{" withposter" if po else ""}">{po}<div>'
                f'<h1>{escape(f["title"])}</h1>{summary}'
                '<dl class="facts">' + "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts) + "</dl></div></div>"
                + (f'<p class="src">Source: {"; ".join(src)}</p>' if src else "")
                + (f'<h3>Also at the festival</h3><ul class="plain">' + "".join(f'<li>{self.flink(o["id"], year=True)}</li>' for o in other) + "</ul>" if other else ""))
        self.page(f"films/{fid}.html", f"{f['title']} ({f['year']})", body, "films.html",
                  desc=f"{f['title']} at the {f['year']} Mill Valley Film Festival.")

    def person_page(self, pid):
        p = self.P[pid]
        rows = []
        for y in p["years"]:
            roles = p["roles"].get(str(y), [])
            films = [fid for fid in p["films"] if self.F[fid]["year"] == y]
            evs = [ev for ev in self.E[y]["events"] if any(x["id"] == pid for x in ev["people"])]
            items = [self.flink(fid) for fid in films] + [escape(ev["title"] or "") for ev in evs]
            rows.append(f'<tr><td><a href="../years/{y}.html">{y}</a></td><td>{escape(", ".join(roles))}</td>'
                        f'<td>{"<br>".join(items)}</td></tr>')
        n = len(p["years"])
        lede = f'At the Mill Valley Film Festival in {plural(n, "year")}' + (f', {p["years"][0]}–{p["years"][-1]}' if n > 1 else f', {p["years"][0]}')
        body = (f'<p class="crumbs"><a href="../people.html">People</a></p><h1>{escape(p["name"])}</h1>'
                f'<p class="lede">{lede}.</p><div class="tw"><table><tr><th>Year</th><th>Role</th><th>Films and events</th></tr>'
                + "".join(rows) + "</table></div>"
                '<p class="note">Roles as named in the programmes: director, guest (expected at the screening), cast, '
                'honoree, staff, and the parts people played in tributes and panels. People with the same name are merged.</p>')
        self.page(f"people/{pid}.html", p["name"], body, "people.html")

    def films_index(self):
        items = sorted(self.F, key=lambda i: (self.F[i]["title"].lower().lstrip("'\"¡¿").removeprefix("the "), self.F[i]["year"]))
        chips = "".join(f'<button class="chip" data-k="y" data-v="{y}" aria-pressed="false">{y}</button>' for y in self.film_years)
        body = (f'<h1>Films <span class="count">{len(self.F):,}</span></h1>'
                f'<p class="lede">Every film read from the {len(self.film_years)} festival years that have a film list so far.</p>'
                '<div class="filter" data-target="ul.films li"><input type="search" placeholder="Filter by title, director, country…" '
                f'aria-label="Filter films"><span class="shown"></span><div class="chips">{chips}</div></div>'
                '<ul class="films">' + "".join(self.film_li(i, "", True) for i in items) + "</ul>")
        self.page("films.html", "Films", body, "films.html", depth=0)

    def posters_page(self):
        by_year = defaultdict(list)
        for fid in self.posters:
            by_year[self.F[fid]["year"]].append(fid)
        n = len(self.posters)
        body = (f'<h1>Poster wall</h1><p class="lede">Posters for {n:,} of the {len(self.F):,} films in the explorer, newest '
                'festival first. They come from the films\' Wikipedia articles and Wikimedia Commons, and from the films\' '
                'own websites, distributors and other festivals; each film page says where its poster came from. The '
                'festival\'s own images are stills, not posters, so they are not used here.</p>'
                '<p class="az">' + "".join(f'<a href="#y{y}">{y}</a>' for y in sorted(by_year, reverse=True)) + "</p>")
        for y in sorted(by_year, reverse=True):
            ids = sorted(by_year[y], key=lambda i: self.F[i]["title"].lower())
            body += (f'<h2 id="y{y}">{y} <span class="count">{len(ids)}</span> <a class="count" href="years/{y}.html">the {y} festival →</a></h2>'
                     '<ul class="pwall">' + "".join(f'<li><a href="films/{i}.html">{self.poster(i, "")}<span class="ft">{escape(self.F[i]["title"])}</span></a></li>' for i in ids) + "</ul>")
        self.page("posters.html", "Poster wall", body, "posters.html", depth=0)

    def people_index(self):
        ret = sorted((p for p in self.P.values() if len(p["years"]) >= 3),
                     key=lambda p: (-len(p["years"]), p["name"]))
        dirs = sorted((p for p in self.P.values() if any("director" in r for r in p["roles"].values())),
                      key=lambda p: p["name"].split()[-1].lower())
        body = [f'<h1>People <span class="count">{len(self.P):,}</span></h1>',
                '<p class="lede">Directors, guests, cast, honorees, panelists and staff named in the programmes.</p>',
                f'<h2>Regulars: at the festival in three or more years <span class="count">{len(ret)}</span></h2>',
                '<ul class="cols">' + "".join(f'<li>{self.plink(p["id"], "")} <span class="count">{len(p["years"])}</span></li>' for p in ret) + "</ul>",
                f'<h2>Directors <span class="count">{len(dirs):,}</span></h2>',
                '<div class="filter" data-target="ul.dl li"><input type="search" placeholder="Filter directors" aria-label="Filter directors"><span class="shown"></span></div>',
                '<ul class="cols dl">' + "".join(f'<li data-n="{escape(p["name"])}">{self.plink(p["id"], "")} <span class="count">{", ".join(map(str, p["years"]))}</span></li>' for p in dirs) + "</ul>"]
        self.page("people.html", "People", "".join(body), "people.html", depth=0)

    def honorees(self):
        rows = []
        for y in self.years:
            for ev in self.E[y]["events"]:
                if ev.get("kind") in ("tribute", "spotlight", "award", "conversation"):
                    hon = [x for x in ev["people"] if x.get("role") in ("honoree", None, "speaker") and x["id"] in self.P][:3]
                    rows.append(f'<tr><td><a href="years/{y}.html">{y}</a></td><td>{escape(ev.get("kind") or "")}</td>'
                                f'<td><b>{escape(ev.get("title") or "")}</b><br>{", ".join(self.plink(h["id"], "") for h in hon)}</td></tr>')
            for a in self.E[y]["awards"]:
                rows.append(f'<tr><td><a href="years/{y}.html">{y}</a></td><td>award</td><td><b>{escape(a.get("name") or "")}</b><br>'
                            f'{escape(a.get("recipient") or "")}</td></tr>')
        body = ('<h1>Tributes, spotlights and awards</h1><p class="lede">The festival\'s tributes and spotlights on actors and '
                'directors, and the MVFF Award, as printed in each year\'s programme.</p><div class="tw"><table>'
                '<tr><th>Year</th><th>Kind</th><th>Event and honoree</th></tr>' + "".join(rows) + "</table></div>")
        self.page("honorees.html", "Tributes", body, "honorees.html", depth=0)

    def countries(self):
        cs = sorted(self.country_films.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        top = len(cs[0][1]) if cs else 1
        body = [f'<h1>Countries <span class="count">{len(cs)}</span></h1><p class="lede">Where the films came from, as the programmes print it.</p>',
                '<div class="tw"><table><tr><th>Country</th><th>Films</th><th></th></tr>']
        for c, ids in cs:
            body.append(f'<tr id="{slug(c)}"><td>{escape(c)}</td><td>{len(ids)}</td><td><span class="bar" style="width:{max(2, 220 * len(ids) // top)}px"></span></td></tr>')
        body.append("</table></div>")
        for c, ids in cs[:60]:
            body.append(f'<h2 id="l-{slug(c)}">{escape(c)} <span class="count">{len(ids)}</span></h2><ul class="films">'
                        + "".join(self.film_li(i, "", True) for i in sorted(ids, key=lambda i: (self.F[i]["year"], self.F[i]["title"]))) + "</ul>")
        self.page("countries.html", "Countries", "".join(body), "countries.html", depth=0)

    def venues(self):
        vs = sorted(self.V.values(), key=lambda v: -v["screenings"])
        body = ('<h1>Venues</h1><p class="lede">Where the screenings were, as the programmes list them (screens of one '
                'cinema are counted together). Counts cover only years with screening times in the explorer.</p>'
                '<div class="tw"><table><tr><th>Venue</th><th>Screenings</th><th>Years</th></tr>'
                + "".join(f'<tr><td>{escape(v["name"])}</td><td>{v["screenings"]:,}</td><td>{", ".join(map(str, v["years"]))}</td></tr>' for v in vs)
                + "</table></div>")
        self.page("venues.html", "Venues", body, "countries.html", depth=0)

    def archive(self):
        inv = self.inv
        today = "20261118"
        before = lambda i: bool(i["first_capture"]) and i["first_capture"] < today
        kinds = Counter((i["kind"], before(i)) for i in inv)
        sv = (self.saved or {}).get("urls", {})
        saved_k = Counter(i["kind"] for i in inv if sv.get(i["url"], {}).get("status") == "success")
        guides = [i for i in inv if i["kind"].startswith("guide")]
        g_missing = [i for i in guides if not i["first_capture"]]
        rows = []
        for kind, label in (("guide-issuu", "Programme guides on Issuu"), ("guide-pdf", "Programme guide PDFs"),
                            ("page", "Pages on mvff.com and cafilm.org"), ("post", "News posts"),
                            ("film", "Film pages"), ("person", "Director pages"), ("pdf", "Other PDFs"),
                            ("file", "Other files")):
            have, miss = kinds.get((kind, True), 0), kinds.get((kind, False), 0)
            if have + miss:
                rows.append(f"<tr><td>{label}</td><td>{have + miss:,}</td><td class=ok>{have:,}</td>"
                            f"<td class=gap>{miss:,}</td><td>{saved_k.get(kind, 0):,}</td></tr>")
        saved = self.saved
        body = ['<h1>What the Wayback Machine holds</h1>',
                '<p class="lede">The festival has lived on many websites since 2000: static film notes, a Drupal site, '
                'yearly subdomains, two ticketing systems and today\'s WordPress and festival app. Its printed programme '
                'guides, back to 1978, are now on Issuu. Here is what was online in November 2026, checked against the '
                'Wayback Machine\'s capture index, and what we did about the gaps.</p>',
                '<h2>Live pages and documents, checked 18 November 2026</h2>',
                '<div class="tw"><table><tr><th>What</th><th>Live</th><th>Archived before</th><th>Never archived</th><th>Saved by us</th></tr>'
                + "".join(rows) + "</table></div>"]
        imgs = kinds.get(("image", False), 0)
        body.append(f'<p class="note">Images ({imgs:,} never captured on their own) are not sent separately: Save Page Now '
                    'captures the images a page shows when it saves the page. We left out 21 non-PDF files from the sites\' '
                    'media libraries (drafts, documents, settings) and 81 PDFs that look internal or personal (sponsor decks, '
                    'guest lists, job descriptions, release forms, login instructions, drafts).</p>')
        if saved:
            body.append(f'<p class="callout">On {escape(saved.get("date", ""))} we sent {saved.get("sent", 0):,} never-archived '
                        f'addresses to Save Page Now: {saved.get("success", 0):,} are now in the Wayback Machine'
                        + (f', {saved.get("failed", 0):,} could not be captured' if saved.get("failed") else "")
                        + (f' and {saved.get("queued", 0):,} were still waiting when this page was built ({escape(saved.get("checked", ""))})'
                           if saved.get("queued") else "") + ".</p>")
        body.append('<h2>Programme guides, year by year</h2><div class="tw"><table><tr><th>Year</th><th>Edition</th>'
                    '<th>Guide</th><th>In the Wayback Machine</th><th>Films in this explorer</th></tr>')
        gmap = defaultdict(list)
        for g in guides:
            m = re.search(r"(\d\d)", g["source"])
            if m:
                gmap[int(m.group(1))].append(g)
        for y in self.years:
            e = self.E[y]
            gs = gmap.get(e["edition"], [])
            cells = "<br>".join(f'<a href="{escape(g["url"])}">{escape(g["url"].rsplit("/", 1)[-1])}</a>' for g in gs) or "—"
            def gst(g):
                if g["first_capture"] and g["first_capture"] < today:
                    return f'<span class=ok>since {g["first_capture"][:4]}</span>'
                if sv.get(g["url"], {}).get("status") == "success" or (g["first_capture"] or "") >= today:
                    return '<span class=gap>never</span> → saved 18 Nov 2026'
                return '<span class=gap>never</span>'
            st = "<br>".join(gst(g) for g in gs) or "—"
            pdf = any(s["kind"] == "pdf" for s in e["sources"])
            rows2 = f'{len(e["films"])}' + (" (from a programme PDF)" if pdf and e["films"] else "")
            body.append(f'<tr><td><a href="years/{y}.html">{y}</a></td><td>{ordinal(e["edition"])}</td><td>{cells}</td><td>{st}</td><td>{rows2}</td></tr>')
        body.append("</table></div>")
        g_missing = [g for g in guides if not before(g)]
        body.append(f'<p class="note">{len(g_missing)} of {len(guides)} programme guides on Issuu had never been captured '
                    'before 18 November 2026. A capture of an Issuu document holds the reader page; whether the page images '
                    'were saved with it varies.</p>')
        self.page("archive.html", "What's archived", "".join(body), "archive.html", depth=0)

    def programmes(self):
        ft = DATA / "fulltext.json"
        ft = json.load(open(ft)) if ft.exists() else {"pages": 0, "by_year": {}}
        decades = sorted({int(y) // 10 * 10 for y in ft["by_year"]})
        opts = "".join(f'<option value="{d}s">{d}s</option>' for d in decades)
        rows = []
        for y in self.years:
            e = self.E[y]
            n = ft["by_year"].get(str(y), 0)
            g = " · ".join(f'<a href="{escape(x["page"])}">guide</a>' for x in e["guides"][:1])
            rows.append(f'<tr><td><a href="years/{y}.html">{y}</a></td><td>{ordinal(e["edition"])}</td><td>{n:,}</td><td>{g}</td></tr>')
        body = f"""<h1>Search the programmes</h1>
<p class="lede">Every page of the festival's printed programme guides, 1978–2026, read by OCR: {ft["pages"]:,} pages. Search for a
film, a filmmaker, an actor, a venue or a sponsor; each result opens that page of the programme.</p>
<form class="bigsearch" role="search" id="pfform"><input id="pq" type="search" placeholder="e.g. Kieslowski, Sequoia, Robin Williams…"
aria-label="Search the programme guides"><select id="pdec" aria-label="Decade" style="font:16px var(--sans);border-radius:6px;padding:0 8px">
<option value="">All years</option>{opts}</select><button>Search</button></form>
<p id="pstatus" class="note" role="status"></p><ol id="presults" class="plain"></ol>
<p><button id="pmore" class="chip hide" type="button">Show more results</button></p>
<noscript><p>Searching the programmes needs JavaScript. The guides themselves are linked from each <a href="index.html">year page</a>.</p></noscript>
<p class="note">Text comes from OCR of the festival's scans on Issuu (1978–2026) and from the programme PDFs archived in the
Wayback Machine (2001–2011, 2024–2026), so expect misreadings, especially in schedule grids and display type. Excerpts are
short; the full pages are the festival's, on Issuu and in the Wayback Machine.</p>
<h2>Pages indexed, by year</h2><div class="tw"><table><tr><th>Year</th><th>Festival</th><th>Pages</th><th>Guide</th></tr>{"".join(rows)}</table></div>
<script type="module">
const form = document.getElementById("pfform"), q = document.getElementById("pq"), dec = document.getElementById("pdec");
const out = document.getElementById("presults"), status = document.getElementById("pstatus"), more = document.getElementById("pmore");
const pf = await import("./pagefind/pagefind.js");
await pf.options({{ excerptLength: 24 }});
let results = [], shown = 0;
const ord = n => n + ((n % 100 >= 11 && n % 100 <= 13) ? "th" : ({{1: "st", 2: "nd", 3: "rd"}}[n % 10] || "th"));
const esc = s => String(s).replace(/[&<>"]/g, c => ({{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}})[c]);
async function show(n) {{
  const batch = results.slice(shown, shown + n);
  const data = await Promise.all(batch.map(r => r.data()));
  out.insertAdjacentHTML("beforeend", data.map(d => `<li class="card"><a href="${{esc(d.meta.view)}}"><b>${{esc(d.meta.title)}}</b></a>
    <span class="sub">${{ord(+d.meta.edition)}} festival · <a href="years/${{d.meta.year}}.html">year page</a> · <a href="${{esc(d.meta.wayback)}}">Wayback Machine copy</a></span>
    <p style="margin:.4em 0 0">…${{d.excerpt}}…</p></li>`).join(""));
  shown += batch.length;
  more.classList.toggle("hide", shown >= results.length);
}}
async function run() {{
  const term = q.value.trim();
  try {{ const u = new URL(location.href); term ? u.searchParams.set("q", term) : u.searchParams.delete("q"); dec.value ? u.searchParams.set("d", dec.value) : u.searchParams.delete("d"); history.replaceState(null, "", u); }} catch (e) {{}}
  out.innerHTML = ""; shown = 0; results = [];
  if (!term) {{ status.textContent = ""; more.classList.add("hide"); return; }}
  status.textContent = "Searching…";
  const r = await pf.search(term, dec.value ? {{ filters: {{ decade: dec.value }} }} : {{}});
  results = r.results.sort((a, b) => b.score - a.score);
  status.textContent = results.length.toLocaleString() + " pages";
  await show(20);
}}
form.addEventListener("submit", e => {{ e.preventDefault(); run(); }});
dec.addEventListener("change", run);
more.addEventListener("click", () => show(20));
const p = new URL(location.href).searchParams;
if (p.get("q")) {{ q.value = p.get("q"); if (p.get("d")) dec.value = p.get("d"); run(); }}
</script>"""
        self.page("programmes.html", "Search the programmes", body, "programmes.html", depth=0)

    def about(self):
        prog = [y for y in self.film_years if any(s["kind"] == "pdf" for s in self.E[y]["sources"]) and y <= 2011]
        body = f"""<h1>About this explorer</h1>
<p class="lede">An index of the Mill Valley Film Festival's films, people and programmes, built from the festival's own
printed programmes and websites as they survive in the Wayback Machine and online.</p>
<h2>Where the film lists come from</h2>
<ul>
<li><b>{prog[0]}–{prog[-1]}:</b> the festival's printed programmes, saved as PDFs from cafilm.org and mvff.com in the
Wayback Machine. Claude subagents read every page of each programme into structured records (title, directors,
countries, year, running time, section, screenings, guests, tributes and events). The one-line film descriptions on
those years' pages are written by Claude, not copied from the programme; each film page links to the archived
programme it came from.</li>
<li><b>2023–2024:</b> the programme data embedded in mvff.com's "browse the program" page, read from Wayback Machine
captures taken during each festival.</li>
<li><b>2025–2026:</b> the festival app at app.mvff.com, film by film, from the Wayback Machine where captured and from
the live site otherwise. The short descriptions on these pages are the festival's own one-line loglines.</li>
<li><b>Other years</b> link to the festival's scans of its programme guides (on Issuu, via mvff.com's guide archive),
but their films are not in the explorer yet.</li>
</ul>
<p>Printed programmes disagree with themselves now and then (dates, spellings, running times); each year page has the
reading notes. Names are as printed; different people with the same name are merged.</p>
<h2>Web archives</h2>
<p>We checked every page, film record and document on mvff.com and cafilm.org, and every programme guide, against
the Wayback Machine and saved what had never been captured; see <a href="archive.html">What's archived</a>.</p>
<h2 id="accessibility">Accessibility</h2>
<p>Pages are plain HTML with headings, landmarks, a skip link and visible focus, work without JavaScript (except
filtering and search), and follow the system's light or dark setting. If something does not work for you, email
<a href="mailto:info@archive.org">info@archive.org</a>.</p>
<h2>Who made this</h2>
<p>This site was made by Claude, an AI model made by Anthropic, working in Claude Code at the direction of Mark Graham
(Internet Archive). Mark Graham decided what it should be and what it should cover; Claude did the research and wrote
the code. Built {BUILT}. It is a Wayback Machine Labs experiment and is not affiliated with the Mill Valley Film
Festival or the California Film Institute.</p>"""
        self.page("about.html", "About", body, "about.html", depth=0)

    def search(self):
        rows = []
        for f in self.F.values():
            meta = self.film_meta(f)
            rows.append(["film", f"films/{f['id']}.html", f"{f['title']} ({f['year']})",
                         " ".join([f["title"], f.get("original_title") or "", meta, str(f["year"]), f.get("section") or "",
                                   " ".join(self.P[g["id"]]["name"] for g in f["guests"] if g["id"] in self.P)]), meta])
        for p in self.P.values():
            rows.append(["person", f"people/{p['id']}.html", p["name"], p["name"], ", ".join(map(str, p["years"]))])
        (PUBLIC / "search.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
        body = ('<h1>Search</h1><form class="bigsearch" role="search" onsubmit="return false"><input id="q" type="search" '
                'placeholder="Film, director, guest, country, year…" aria-label="Search" autofocus></form>'
                '<p id="status" class="note" role="status"></p><ul id="results" class="plain"></ul>'
                '<noscript><p>Search needs JavaScript; the <a href="films.html">film list</a> works without it.</p></noscript>')
        self.page("search.html", "Search", body, "search.html", depth=0)

    def misc(self):
        self.page("404.html", "Not found", '<h1>Page not found</h1><p><a href="/mvff/index.html">Back to the festival years</a></p>', depth=0)
        (PUBLIC / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n")
        (PUBLIC / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                            + "".join(f"<url><loc>{BASE_URL}{u}</loc></url>" for u in self.urls if u != "404.html")
                                            + "</urlset>\n")
        print(f"{len(self.urls)} pages")


if __name__ == "__main__":
    Site().build()
