"""Page text for every archived programme PDF (raw/pdf): the PDF's own text layer, or Tesseract OCR of the page
rendered at 200 dpi when the text layer has fewer than 40 words (image-only calendars, scanned pages).

    python3 -m mv.pdfocr          -> raw/pdftext/<pdf name>/page_NNN.txt (+ .ocr marker when OCR was used)
"""
import concurrent.futures as cf
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF, OUT = ROOT / "raw" / "pdf", ROOT / "raw" / "pdftext"
SKIP = {"2007_souvenir", "2007_catalog", "2008_guide_b"}   # truncated copy; duplicates of 2007_guide / 2008_guide


def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return next((int(l.split()[-1]) for l in out.splitlines() if l.startswith("Pages:")), 0)


def one(job):
    pdf, n = job
    d = OUT / pdf.stem
    f = d / f"page_{n:03d}.txt"
    if f.exists():
        return
    t = subprocess.run(["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(pdf), "-"],
                       capture_output=True, text=True).stdout
    if len(t.split()) < 40:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["pdftoppm", "-r", "200", "-f", str(n), "-l", str(n), "-png", str(pdf), f"{tmp}/p"],
                           capture_output=True)
            png = next(Path(tmp).glob("p*.png"), None)
            if png:
                o = subprocess.run(["tesseract", str(png), "stdout", "-l", "eng"], capture_output=True, text=True).stdout
                if len(o.split()) > len(t.split()):
                    t = o
                    (d / f"page_{n:03d}.ocr").write_text("")
    f.write_text(t)


def main():
    jobs = []
    for pdf in sorted(PDF.glob("*.pdf")):
        if pdf.stem in SKIP:
            continue
        (OUT / pdf.stem).mkdir(parents=True, exist_ok=True)
        jobs += [(pdf, n) for n in range(1, pages(pdf) + 1)]
    with cf.ThreadPoolExecutor(4) as ex:
        list(ex.map(one, jobs))
    ocr = len(list(OUT.glob("*/*.ocr")))
    print(len(jobs), "PDF pages;", ocr, "needed OCR")


if __name__ == "__main__":
    main()
