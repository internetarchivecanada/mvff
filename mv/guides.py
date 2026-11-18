"""Fetch every programme-guide page listed on mvff.com (pages whose slug has 'program' or 'souvenir') and record
the Issuu document or PDF each one shows -> raw/issuu_map.tsv (slug <TAB> issuu ids / pdf paths).

    python3 -m mv.guides
"""
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw"
S = requests.Session()
S.headers["User-Agent"] = "WaybackLabs-FestivalExplorer/0.1 (Internet Archive research)"


def main():
    pages = json.loads((RAW / "live" / "mvff.com_pages.json").read_text())
    slugs = sorted({p["slug"] for p in pages if re.search(r"program|souvenir", p["slug"])})
    out = []
    (RAW / "livepages").mkdir(exist_ok=True)
    for s in slugs:
        f = RAW / "livepages" / f"{s}.html"
        if not f.exists():
            r = S.get(f"https://www.mvff.com/{s}/", timeout=60)
            f.write_text(r.text)
            time.sleep(10)
        t = f.read_text()
        ids = sorted(set(re.findall(r"issuu\.com/embed\.html\?[^\"']*?[?&;]d=([\w.-]+)", t))
                     | set(re.findall(r"issuu\.com/smithrafaelfilmcenter/docs/([\w.-]+)", t)))
        pdfs = sorted(set(re.findall(r"wp-content/uploads/[^\"'\s]+?\.pdf", t, re.I))
                      - {p for p in re.findall(r"wp-content/uploads/[^\"'\s]+?\.pdf", t, re.I)
                         if re.search(r"privacy|terms|schedule_digital", p, re.I)})
        out.append(f"{s}\t{' '.join(ids + pdfs)}")
        print(out[-1], flush=True)
    (RAW / "issuu_map.tsv").write_text("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
