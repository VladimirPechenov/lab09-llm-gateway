"""Render report for visual QA and assert page count."""

from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "tmp/pdfs"
target.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(ROOT / "docs/report.pdf")
print("Pages:", len(doc))
thumbs = []
for i, page in enumerate(doc):
    page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(target / f"page-{i + 1}.png")
    text = page.get_text()
    print(i + 1, len(text), text[:75].replace("\n", " "))
    im = Image.open(target / f"page-{i + 1}.png").convert("RGB")
    im.thumbnail((420, 594))
    thumbs.append(im)
sheet = Image.new("RGB", (420 * 3, 620 * ((len(thumbs) + 2) // 3)), "#cad4df")
draw = ImageDraw.Draw(sheet)
for i, im in enumerate(thumbs):
    x, y = (i % 3) * 420, (i // 3) * 620
    sheet.paste(im, (x, y))
    draw.text((x + 10, y + 595), str(i + 1), fill="black")
sheet.save(target / "contact.png")
assert len(doc) == 6
