"""Fetch the Save Page Now results for this project's URLs from the studio queue (confinv.spn_job) -> data/saved.json.

    python3 -m mv.saved

The URLs are data/save_list.txt plus the Issuu programme guides queued on 18 November 2026 (raw/spn_issuu.txt).
"""
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, RAW = ROOT / "data", ROOT / "raw"
DATE = "18 November 2026"


def main():
    urls = [u.strip() for f in (DATA / "save_list.txt", RAW / "spn_issuu.txt") if f.exists()
            for u in f.read_text().splitlines() if u.strip()]
    sql = ("COPY (SELECT host, coalesce(status, 'queued'), coalesce(timestamp, ''), replace(replace(coalesce(message, ''), E'\\t', ' '), E'\\n', ' ') FROM spn_job "
           "WHERE host LIKE 'https://%mvff%' OR host LIKE 'https://%cafilm%' OR host LIKE 'https://issuu.com/%') TO STDOUT")
    out = subprocess.run(["ssh", "studioj", f'/opt/homebrew/bin/psql -h /tmp confinv -Atc "{sql}"'],
                         capture_output=True, text=True, check=True).stdout
    st = {}
    for line in out.splitlines():
        u, s, ts, msg = (line.split("\t") + [""])[:4]
        # a refusal because "the same snapshot had been made" minutes earlier means the page is in the archive
        ok = s in ("success", "recent") or (s == "refused" and "same snapshot" in msg)
        gone = s == "error" and "cannot find" in msg          # the live site answers 404: nothing to save
        st[u] = {"status": "success" if ok else ("not-live" if gone else s), "timestamp": ts,
                 "message": msg[:200] if not ok else ""}
    res = {u: st.get(u, {"status": "queued", "timestamp": ""}) for u in urls}
    c = Counter(v["status"] for v in res.values())
    summary = {"date": DATE, "sent": len(urls), "success": c.get("success", 0),
               "failed": c.get("error", 0) + c.get("timeout", 0), "not_live": c.get("not-live", 0), "queued": c.get("queued", 0) + c.get("pending", 0),
               "checked": time.strftime("%Y-%m-%d %H:%M")}
    (DATA / "saved.json").write_text(json.dumps({**summary, "urls": res}, indent=0))
    print(summary)


if __name__ == "__main__":
    main()
