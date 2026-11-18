"""Render the landing-page cover (1200x630) to cover/mvff-cover.jpg from data/festival.json.

    python3 cover/make.py
"""
import json
import subprocess
from pathlib import Path

here = Path(__file__).parent
d = json.loads((here.parent / "data" / "festival.json").read_text())
E = {int(k): v for k, v in d["editions"].items()}
W, H = 1200, 630
nf = len(d["films"])
cells = []
x0, y0, cw, ch, gap = 640, 132, 62, 50, 8
for i, y in enumerate(sorted(E)):
    r, c = divmod(i, 7)
    x, yy = x0 + c * (cw + gap), y0 + r * (ch + gap)
    has = bool(E[y]["films"])
    cells.append(f'<g><rect x="{x}" y="{yy}" width="{cw}" height="{ch}" rx="6" class="{"on" if has else "off"}"/>'
                 f'<text x="{x + cw / 2}" y="{yy + ch / 2 + 7}" class="{"ton" if has else "toff"}">{str(y)[2:]}</text></g>')
html = f"""<!doctype html><meta charset=utf-8><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#16201c;font-family:Georgia,serif}}
svg{{position:absolute;inset:0}}
.on{{fill:#d9a441}} .off{{fill:none;stroke:#d9a441;stroke-width:2;stroke-dasharray:5 4;opacity:.75}}
text{{font:700 22px -apple-system,Helvetica,sans-serif;text-anchor:middle}}
.ton{{fill:#16201c}} .toff{{fill:#d9a441;opacity:.85}}
h1{{position:absolute;left:60px;top:150px;margin:0;color:#fbf5e6;font:700 76px/1.0 Georgia,serif;letter-spacing:-1px}}
h1 em{{display:block;color:#d9a441;font-style:normal;font-weight:400;font-size:62px;margin-top:10px}}
p{{position:absolute;left:62px;top:440px;margin:0;color:#efe6d0;font:600 30px/1.3 -apple-system,Helvetica,sans-serif}}
p b{{color:#d9a441}}
</style>
<svg viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#16201c"/>
<path d="M0 630 L0 560 L150 520 L300 470 L420 430 L520 455 L640 395 L760 450 L900 500 L1050 540 L1200 560 L1200 630 Z" fill="#22302a"/>
<path d="M0 630 L0 600 L200 575 L380 560 L560 585 L760 570 L980 590 L1200 580 L1200 630 Z" fill="#2c3d35"/>
<rect x="0" y="0" width="{W}" height="10" fill="#d9a441"/>
{''.join(cells)}</svg>
<h1>Mill Valley<br>Film Festival<em>Explorer</em></h1>
<p><b>{nf:,}</b> films · <b>49</b> festivals<br>1978–2026</p>"""
(here / "cover.html").write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
png = here / "cover.png"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                f"--screenshot={png}", f"file://{(here / 'cover.html').resolve()}"], check=True, capture_output=True)
subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "88", str(png), "--out",
                str(here / "mvff-cover.jpg")], check=True, capture_output=True)
png.unlink()
print("wrote", here / "mvff-cover.jpg")
