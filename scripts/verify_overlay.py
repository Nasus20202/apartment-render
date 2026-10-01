"""Overlay the Blender plan render on the source PDF at identical scale to check alignment.

    uv run python scripts/verify_overlay.py

Writes renders/shell_overlay.png: the PDF in black, the Blender render tinted red at 45% opacity.
"""

import json
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops, ImageOps

ROOT = Path(__file__).resolve().parent.parent
plan = json.loads((ROOT / "data" / "floorplan.json").read_text())
mapping = json.loads((ROOT / "renders" / "shell_topdown_map.json").read_text())

mm_per_pt = plan["scale"]["mm_per_pt"]
ox, oy = plan["origin_pt"]["x"], plan["origin_pt"]["y"]
fx0, fx1, fy0, fy1 = mapping["frame_m"]
px_per_m = mapping["px_per_m"]

# Blender frame (metres) -> PDF displayed-page rect (points)
clip = pymupdf.Rect(
    ox + fx0 * 1000 / mm_per_pt,
    oy - fy1 * 1000 / mm_per_pt,
    ox + fx1 * 1000 / mm_per_pt,
    oy - fy0 * 1000 / mm_per_pt,
)
zoom = px_per_m * mm_per_pt / 1000  # render pixels per PDF point

page = pymupdf.open(ROOT / "references" / "floor-plan.pdf")[0]
pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip)
pdf = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

render = Image.open(ROOT / "renders" / "shell_topdown.png").convert("RGB")
pdf = pdf.resize(render.size)  # guards against an off-by-one pixel from rounding

tint = ImageOps.colorize(ImageOps.grayscale(render), black=(200, 0, 0), white=(255, 255, 255))
out = ImageChops.multiply(Image.blend(Image.new("RGB", render.size, "white"), tint, 0.45), pdf)
out.save(ROOT / "renders" / "shell_overlay.png")
print("wrote renders/shell_overlay.png", out.size, f"zoom={zoom:.3f}")
