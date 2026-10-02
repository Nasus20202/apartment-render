import sys
from pathlib import Path

import matplotlib
import pymupdf

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

d = pymupdf.open(Path(__file__).resolve().parent.parent / "references" / "floor-plan.pdf")
p = d[0]
M = p.rotation_matrix
segs = []
for x in p.get_drawings():
    w = x.get("width") or 0.3
    col = "k" if x.get("color") in (None, (0, 0, 0)) else "orange"
    for it in x["items"]:
        if it[0] == "l":
            pts = [it[1] * M, it[2] * M]
        elif it[0] == "c":
            pts = [it[1] * M, it[2] * M, it[3] * M, it[4] * M]
        elif it[0] == "re":
            r = it[1]
            pts = [
                pymupdf.Point(r.x0, r.y0) * M,
                pymupdf.Point(r.x1, r.y0) * M,
                pymupdf.Point(r.x1, r.y1) * M,
                pymupdf.Point(r.x0, r.y1) * M,
                pymupdf.Point(r.x0, r.y0) * M,
            ]
        elif it[0] == "qu":
            q = it[1]
            pts = [q.ul * M, q.ur * M, q.lr * M, q.ll * M, q.ul * M]
        else:
            continue
        segs.append(([q.x for q in pts], [q.y for q in pts], w, col))


def tile(name, x0, x1, y0, y1, step=5):
    fig, ax = plt.subplots(figsize=(14, 14 * (y1 - y0) / (x1 - x0)))
    for xs, ys, w, c in segs:
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
            continue
        ax.plot(xs, ys, lw=w * 3, color=c)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(x0, x1 + 1, step))
    ax.set_yticks(np.arange(y0, y1 + 1, step))
    ax.tick_params(labelsize=6)
    ax.tick_params(axis="x", rotation=90)
    ax.grid(lw=0.2, color="c")
    fig.savefig(name, dpi=110, bbox_inches="tight")
    plt.close(fig)


for a in sys.argv[1:]:
    n, *v = a.split(",")
    tile(n, *map(float, v))
