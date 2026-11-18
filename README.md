# Mill Valley Film Festival Explorer

An index of the films, people, tributes and programme guides of the
[Mill Valley Film Festival](https://www.mvff.com/) (Marin County, California, 1978–2026), and a record of what the
Wayback Machine holds of the festival's websites and programmes.

Live: https://wayback-labs.sf.archive.org/mvff/ (Wayback Machine Labs studio, static tile `mvff`).

Not affiliated with the Mill Valley Film Festival or the California Film Institute (CAFILM).

## Sources

| Years | Source |
|---|---|
| 2001–2011 | The printed programmes, archived as PDFs on cafilm.org and mvff.com (Wayback Machine). Text by `pdftotext -layout`, page by page; Claude subagents read every page into `data/programmes/<year>.json` following `data/programmes/SCHEMA.md`. Each file's `notes` records judgement calls and printing errors. Film summaries there are written by Claude, not copied. |
| 2021–2022 | Film pages of www.mvff.com as archived in the Wayback Machine (`mv/web2.py`). |
| 2023–2024 | The `window.FILM_MANIFEST` programme data embedded in www.mvff.com/browse-program/, from captures taken during each festival (`mv/web.py`). |
| 2025–2026 | The festival app, app.mvff.com/browse and /film/<slug>, from the Wayback Machine where captured, else live (`mv/web.py`). |
| 1978–2026 | The festival's programme guide archive (www.mvff.com/mvff-guide-archive/), which embeds Issuu scans of the printed guides (`mv/guides.py`). Years without a film list link to these. |

## What was archived

`mv/live.py` lists everything live on www.mvff.com and www.cafilm.org (WordPress REST: pages, posts, films,
directors, media) and the 2026 festival app, respecting the sites' 10-second crawl delay. `mv/compare.py` checks
each address and every programme guide (both Issuu accounts) against the Wayback Machine's capture index and writes
`data/inventory.json` and `data/missing.txt`. The missing addresses were sent to Save Page Now from the studio
(`~/conferences/spn_save.py add`, in the conference-inventory repo).

## Build

```
python3 -m mv.live        # live inventory -> raw/live (slow: 10 s per request)
python3 -m mv.guides      # programme guide pages -> raw/issuu_map.tsv
python3 -m mv.web         # 2023-2026 films -> data/web
python3 -m mv.web2        # 2021-2022 films -> data/web
python3 -m mv.compare     # inventory vs Wayback -> data/inventory.json, data/missing.txt
python3 -m mv.model       # -> data/festival.json
python3 -m mv.site        # -> public/ (committed)
```

## Deploy

`/opt/services/mvff` on the studio is a checkout of this repo; Caddy serves `public/` (snippet in `caddy`).
Commit `public/`, push `main`, then `sudo /opt/services/_scripts/deploy-tile plan|deploy mvff --expect <sha>`.

## Who made this

Made by Claude (Anthropic), working in Claude Code at the direction of Mark Graham (Internet Archive).
