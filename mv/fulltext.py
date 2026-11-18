"""Full-text index of every programme page (Issuu guides 1978-2026 + archived programme PDFs) with Pagefind.

    python3 -m mv.fulltext     -> assets/pagefind/ (copied into public/ by mv.site), data/fulltext.json (page counts)

One small HTML file per page is written to raw/fulltext/ (not published) and indexed; each carries metadata for
the search page: year, edition, source, page number, and links to the page on Issuu or in the Wayback Machine's copy
of the PDF. Results show a short excerpt; the full page text is not published as pages of this site.
"""
import json
import re
import shutil
import subprocess
from html import escape
from pathlib import Path

from .model import PROGRAMME_PDF

ROOT = Path(__file__).resolve().parent.parent
RAW, DATA, ASSETS = ROOT / "raw", ROOT / "data", ROOT / "assets"
SITE = RAW / "fulltext"
PDF_YEAR = {"2006_daily": 2006, "2006_schedule": 2006}   # extra 2006 PDFs (the main one is in PROGRAMME_PDF)
PDF_WB = {"2006_daily": ("20061117035356", "http://mvff.com/files/pdfs/MVFF2006_Daily_Schedule.pdf", "Daily schedule"),
          "2006_schedule": ("20061127084219", "http://mvff.com/files/pdfs/MVFF-06FilmScheduleFYI-1.pdf", "Film schedule")}


def clean(t):
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"-\n(\w)", r"\1", t)            # words hyphenated across lines
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def page_html(rec, text):
    meta = "".join(f'<span data-pagefind-meta="{k}:{escape(str(v), quote=True)}"></span>' for k, v in rec.items() if v)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(rec["title"])}</title></head>'
            f'<body><main data-pagefind-body><h1 data-pagefind-meta="title">{escape(rec["title"])}</h1>{meta}'
            f'<span data-pagefind-filter="year">{rec["year"]}</span><span data-pagefind-filter="decade">{rec["year"] // 10 * 10}s</span>'
            f'<div>{escape(text).replace(chr(10), "<br>")}</div></main></body></html>')


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    counts, n = {}, 0
    # Issuu programme guides
    for mf in sorted((RAW / "issuu").glob("*.json")):
        m = json.loads(mf.read_text())
        for t in sorted((RAW / "issuu" / m["doc"]).glob("page_*.txt")):
            p = int(t.stem.split("_")[1])
            text = clean(t.read_text())
            if len(text.split()) < 5:
                continue
            rec = {"title": f"{m['year']} programme guide, page {p}", "year": m["year"], "edition": m["edition"],
                   "page": p, "kind": "guide", "doc": m["doc"],
                   "view": f"https://issuu.com/smithrafaelfilmcenter/docs/{m['doc']}/{p}",
                   "wayback": f"https://web.archive.org/web/2026/https://issuu.com/smithrafaelfilmcenter/docs/{m['doc']}"}
            (SITE / f"g-{m['doc']}-{p:03d}.html").write_text(page_html(rec, text))
            counts[m["year"]] = counts.get(m["year"], 0) + 1
            n += 1
    # archived programme PDFs
    for d in sorted((RAW / "pdftext").iterdir()):
        year = PDF_YEAR.get(d.name) or int(d.name[:4])
        ts, url, label = PDF_WB.get(d.name) or PROGRAMME_PDF[year]
        for t in sorted(d.glob("page_*.txt")):
            p = int(t.stem.split("_")[1])
            text = clean(t.read_text())
            if len(text.split()) < 5:
                continue
            rec = {"title": f"{year} {label.lower()} (PDF), page {p}", "year": year, "edition": year - 1977, "page": p,
                   "kind": "pdf", "doc": d.name, "view": f"https://web.archive.org/web/{ts}id_/{url}#page={p}",
                   "wayback": f"https://web.archive.org/web/{ts}/{url}"}
            (SITE / f"p-{d.name}-{p:03d}.html").write_text(page_html(rec, text))
            counts[year] = counts.get(year, 0) + 1
            n += 1
    out = ASSETS / "pagefind"
    if out.exists():
        shutil.rmtree(out)
    r = subprocess.run(["npx", "-y", "pagefind@1.3.0", "--site", str(SITE), "--output-path", str(out),
                        "--exclude-selectors", "h1"], capture_output=True, text=True)
    print(r.stdout[-800:], r.stderr[-800:])
    (DATA / "fulltext.json").write_text(json.dumps({"pages": n, "by_year": {str(k): v for k, v in sorted(counts.items())}}))
    print(n, "pages indexed across", len(counts), "years")


if __name__ == "__main__":
    main()
