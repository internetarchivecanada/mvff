"""Second poster pass: other-language Wikipedias, for features still without a poster after mv.posters.

For each film: find its Wikidata item (title or original title; a film item whose director matches one of the
festival's directors, same rule as mv.posters), then take the lead image of its article on the Wikipedias that
carry one (non-free posters live on the local-language wikis). Portrait images only (the ratio check in
mv.posters --download-only drops wide ones). Adds entries to data/posters.json with source "wikipedia-<lang>".

    python3 -m mv.posters2 && python3 -m mv.posters --download-only

(TMDB and Letterboxd are not used: their robots.txt files exclude AI agents.)
"""
import json
import time
import urllib.parse

from .posters import DATA, fold, get_json, norm_title, surnames

LANGS = ["fr", "de", "es", "it", "pt", "nl", "sv", "da", "no", "fi", "pl", "cs", "hu", "ro", "tr", "el", "he", "ar",
         "fa", "ja", "ko", "zh", "ru", "uk", "ca", "eu", "is", "et", "hr", "sr", "sl", "id", "th", "vi", "hi", "bn"]
FILM_TYPES = {"Q11424", "Q93204", "Q24862", "Q506240", "Q202866", "Q24869", "Q229390", "Q17013749"}


def find_item(titles, dirnames):
    sn = surnames(dirnames)
    if not sn:
        return None
    for t in titles:
        d = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "wbsearchentities", "search": t, "language": "en", "uselang": "en", "type": "item",
             "limit": "10", "format": "json", "strictlanguage": "0"}))
        ids = [x["id"] for x in (d or {}).get("search", [])
               if norm_title(x.get("label", "")) == norm_title(t) or norm_title(x.get("match", {}).get("text", "")) == norm_title(t)]
        if not ids:
            continue
        e = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "wbgetentities", "ids": "|".join(ids[:10]), "props": "claims|sitelinks", "format": "json"}))
        for qid, ent in ((e or {}).get("entities") or {}).items():
            cl = ent.get("claims", {})
            inst = {c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in cl.get("P31", [])}
            if not inst & FILM_TYPES:
                continue
            dir_ids = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in cl.get("P57", [])]
            dir_ids = [i for i in dir_ids if i]
            if not dir_ids:
                continue
            dl = get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "wbgetentities", "ids": "|".join(dir_ids[:20]), "props": "labels", "format": "json"}))
            labels = " ".join(fold(l.get("value", "")) for v in ((dl or {}).get("entities") or {}).values()
                              for l in (v.get("labels") or {}).values())
            if any(s in labels for s in sn):
                return qid, ent.get("sitelinks", {})
    return None


def lead_image(sitelinks):
    for lang in LANGS:
        sl = sitelinks.get(f"{lang}wiki")
        if not sl:
            continue
        d = get_json(f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "format": "json", "titles": sl["title"], "prop": "pageimages",
             "piprop": "original|name", "pilicense": "any", "redirects": "1"}))
        for p in ((d or {}).get("query", {}).get("pages", {}) or {}).values():
            img = p.get("original", {}).get("source")
            if img and not img.lower().endswith(".svg"):
                return lang, sl["title"], img, p.get("pageimage")
        time.sleep(0.2)
    return None


def main():
    d = json.load(open(DATA / "festival.json"))
    P = d["people"]
    out = json.load(open(DATA / "posters.json"))
    todo = [f for f in d["films"].values() if f["id"] not in out and not f["is_short"] and f["directors"]]
    print(len(todo), "features to try", flush=True)
    found = 0
    for i, f in enumerate(todo):
        dirnames = [P[x]["name"] for x in f["directors"] if x in P]
        titles = [t for t in (f["title"], f.get("original_title")) if t]
        hit = find_item(titles, dirnames)
        if hit:
            qid, sitelinks = hit
            li = lead_image(sitelinks)
            if li:
                lang, title, img, name = li
                out[f["id"]] = {"src": img, "source": f"wikipedia-{lang}",
                                "page": f"https://{lang}.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
                                "credit": f"Wikipedia ({lang}): {title}", "file": name}
                found += 1
                print(f"{i + 1}/{len(todo)} {f['title']} <- {lang} {name}", flush=True)
        if i % 50 == 0:
            json.dump(out, open(DATA / "posters.json", "w"), indent=1, ensure_ascii=False, sort_keys=True)
        time.sleep(0.3)
    json.dump(out, open(DATA / "posters.json", "w"), indent=1, ensure_ascii=False, sort_keys=True)
    print(found, "more posters from other-language Wikipedias")


if __name__ == "__main__":
    main()
