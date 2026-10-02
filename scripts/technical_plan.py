"""Dimensioned technical plan of the flat, as a three-sheet A3 drawing at 1:40.

    uv run python scripts/technical_plan.py

Reads data/floorplan.json, data/furniture.json and data/lighting.json (no Blender needed). Writes
    renders/technical_plan.pdf               all three sheets, vector
    renders/technical_plan_dimensions.png    sheet 1: walls, openings, room and wall dimensions
    renders/technical_plan_fitout.png        sheet 2: furniture with fixtures, clearances
    renders/technical_plan_services.png      sheet 3: sockets, switches, water and drain points, lights

All dimensions are in millimetres, rounded to 10 mm: the developer's plan prints none, so every length is
measured from its vectors (about +-20 mm). Heights and positions not on the plan are marked with *.
"""

import json
import math
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import itertools

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Arc, Circle, Ellipse, Polygon, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FLAT = json.loads((ROOT / "data" / "floorplan.json").read_text())
FURN = json.loads((ROOT / "data" / "furniture.json").read_text())
LIGHTS = json.loads((ROOT / "data" / "lighting.json").read_text())
OUTLETS = {
    k: v for k, v in FLAT["fixtures_reference"]["light_outlets"].items() if not k.startswith("_")
}
ELEC = json.loads((ROOT / "data" / "electrical.json").read_text())["points"]

PAGE_W, PAGE_H = 420, 297  # A3 landscape, mm
S = 25.0  # mm of paper per metre: 1:40
OX, OY = 36.0, 46.0  # paper position of the plan origin (inner SW corner of the living room)
PANEL_X = 246.0  # left edge of the right-hand text panel
INK, GREY = "#111111", "#666666"
DIM = "#222222"

K = FLAT["scale"]["mm_per_pt"] / 1000.0
H = FLAT["heights_m"]
CEIL = H["ceiling"]["value"]


def mx(p):
    return (p - FLAT["origin_pt"]["x"]) * K


def my(p):
    return (FLAT["origin_pt"]["y"] - p) * K


def rect_m(r):
    xs, ys = sorted((mx(r[0]), mx(r[1]))), sorted((my(r[2]), my(r[3])))
    return xs[0], xs[1], ys[0], ys[1]


def P(x, y):
    return OX + x * S, OY + y * S


def mm(v):
    return f"{round(v * 100) * 10:d}"


WALLS = {w["id"]: dict(w, rect=rect_m(w["rect_pt"])) for w in FLAT["walls"]}
OPENINGS = FLAT["openings"]
TAGS = {
    "O_entrance": "D1",
    "O_bedroom_door": "D2",
    "O_bathroom_door": "D3",
    "O_bedroom_balcony": "D4",
    "O_living_balcony": "W1",
    "O_bedroom_window": "W2",
}
ROOMS = [
    dict(r, poly=[(mx(x), my(y)) for x, y in r["polygon_pt"]], tint=t)
    for r, t in zip(FLAT["rooms"], ("#f5f5f5", "#f5f5f5", "#e4e4e4"), strict=True)
]
BALCONY = rect_m(FLAT["balcony"]["slab_pt"])


def area(poly):
    pairs = zip(poly, poly[1:] + poly[:1], strict=True)
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in pairs)) / 2


def opening_geometry(o):
    """(a, b, lo, hi, axis): span along the wall and the host wall's extent across it."""
    xmin, xmax, ymin, ymax = WALLS[o["wall"]]["rect"]
    s = o["span_pt"]
    if o["axis"] == "x":
        a, b = sorted((mx(s[0]), mx(s[1])))
        return a, b, ymin, ymax, "x"
    a, b = sorted((my(s[0]), my(s[1])))
    return a, b, xmin, xmax, "y"


def opening_height(o):
    return H[o["head"]]["value"], H[o["head"]]["assumed"]


def opening_sill(o):
    if "sill" in o:
        return H[o["sill"]]["value"], H[o["sill"]]["assumed"]
    return o["sill_m"], False


class Sheet:
    def __init__(self):
        self.fig = plt.figure(figsize=(PAGE_W / 25.4, PAGE_H / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, PAGE_W)
        self.ax.set_ylim(0, PAGE_H)
        self.ax.axis("off")

    # -- primitives (paper mm) ------------------------------------------------------------------
    def line(self, p, q, lw=0.5, c=INK, ls="-", z=5):
        self.ax.plot(
            [p[0], q[0]], [p[1], q[1]], lw=lw, color=c, ls=ls, zorder=z, solid_capstyle="butt"
        )

    def text(self, x, y, s, size=6, c=INK, ha="center", va="center", rot=0, weight="normal", z=9):
        self.ax.text(
            x, y, s, fontsize=size, color=c, ha=ha, va=va, rotation=rot, fontweight=weight, zorder=z
        )

    def box(self, x0, x1, y0, y1, fc="none", ec=INK, lw=0.5, ls="-", hatch=None, z=3):
        x0, y0 = P(x0, y0)
        x1, y1 = P(x1, y1)
        self.ax.add_patch(
            Rectangle((x0, y0), x1 - x0, y1 - y0, fc=fc, ec=ec, lw=lw, ls=ls, hatch=hatch, zorder=z)
        )

    # -- dimensions (metres in, mm printed) -------------------------------------------------------
    def tick(self, p):
        self.line((p[0] - 1.1, p[1] - 1.1), (p[0] + 1.1, p[1] + 1.1), lw=0.6, c=DIM, z=8)

    def chain(self, vals, at, horizontal=True, ref=None, size=5.5):
        """Dimension chain through vals (metres) along one axis, drawn at `at` on the other axis.
        ref: where the extension lines start (defaults to `at`)."""
        ref = at if ref is None else ref
        sgn = 1 if at >= ref else -1
        pts = [P(v, at) if horizontal else P(at, v) for v in vals]
        self.line(pts[0], pts[-1], lw=0.4, c=DIM, z=8)
        for v, p in zip(vals, pts, strict=True):
            e0 = P(v, ref) if horizontal else P(ref, v)
            e0 = (e0[0], e0[1] + sgn * 0.8) if horizontal else (e0[0] + sgn * 0.8, e0[1])
            e1 = (p[0], p[1] + sgn * 1.5) if horizontal else (p[0] + sgn * 1.5, p[1])
            self.line(e0, e1, lw=0.25, c=DIM, z=7)
            self.tick(p)
        for i, (a, b) in enumerate(itertools.pairwise(vals)):
            c = P((a + b) / 2, at) if horizontal else P(at, (a + b) / 2)
            narrow = (b - a) < 0.16
            off = 1.9 + (2.6 * (i % 2) if narrow else 0)
            if horizontal:
                self.text(
                    c[0], c[1] + sgn * off, mm(b - a), size, DIM, va="bottom" if sgn > 0 else "top"
                )
            else:
                self.text(
                    c[0] + sgn * (off - 0.4),
                    c[1],
                    mm(b - a),
                    size,
                    DIM,
                    rot=90,
                    ha="right" if sgn < 0 else "left",
                )

    # -- architecture -----------------------------------------------------------------------------
    def architecture(self, tone=1.0):
        c = INK if tone == 1.0 else "#8a8a8a"
        for r in ROOMS:
            self.ax.add_patch(
                Polygon([P(*p) for p in r["poly"]], fc=r["tint"], ec="none", zorder=1)
            )
        x0, x1, y0, y1 = BALCONY
        self.box(x0, x1, y0, y1, fc="#ececec", ec="none", z=1)
        for w in WALLS.values():
            a, b, c0, d = w["rect"]
            shaft = w["type"] == "shaft"
            self.box(
                a,
                b,
                c0,
                d,
                fc="white" if shaft else c,
                ec=c,
                lw=0.6,
                hatch="////" if shaft else None,
            )
        self.box(x0, x1, y0, y1, ec=c, lw=0.6, ls="--", z=2)
        self.box(*rect_m(FLAT["balcony"]["railing_pt"]), fc="#444444", ec=c, lw=0.5)
        self.box(*rect_m(FLAT["balcony"]["privacy_screen_pt"]), fc="#999999", ec=c, lw=0.5)
        for o in OPENINGS:
            self.opening(o, c)

    def opening(self, o, c):
        a, b, lo, hi, axis = opening_geometry(o)
        if axis == "x":
            self.box(a, b, lo, hi, fc="white", ec="none", z=4)
            for y in (lo, (lo + hi) / 2, hi):
                self.line(P(a, y), P(b, y), lw=0.35, c=c)
            for x in (a, b):
                self.line(P(x, lo), P(x, hi), lw=0.6, c=c)
        else:
            self.box(lo, hi, a, b, fc="white", ec="none", z=4)
            for x in (lo, (lo + hi) / 2, hi):
                self.line(P(x, a), P(x, b), lw=0.35, c=c)
            for y in (a, b):
                self.line(P(lo, y), P(hi, y), lw=0.6, c=c)
        swing = o.get("swing_dir", (0, 0))
        mid = (lo + hi) / 2
        if o["kind"] == "door":
            hinge = {"east": b, "west": a, "north": b, "south": a}[o["hinge"]]
            self.leaf(axis, hinge, a, mid, swing, b - a, c)
        elif o["kind"] == "window_door":
            for part in o["parts_pt"]:
                if part["kind"] != "door_pair":
                    continue
                p0, p1 = sorted((mx(part["span"][0]), mx(part["span"][1])))
                half = (p1 - p0) / 2
                self.leaf(axis, p0, p0, mid, swing, half, c)
                self.leaf(axis, p1, p1 - half, mid, swing, half, c)

    def leaf(self, axis, hinge, a, mid, swing, w, c):
        """Open door leaf at 90 degrees plus its swing arc. `a` is the low end of the leaf's span."""
        if axis == "x":
            h = P(hinge, mid)
            closed = 0 if hinge == a else 180
            tip = (h[0], h[1] + swing[1] * w * S)
        else:
            h = P(mid, hinge)
            closed = 90 if hinge == a else 270
            tip = (h[0] + swing[0] * w * S, h[1])
        self.line(h, tip, lw=0.7, c=c)
        opened = math.degrees(math.atan2(tip[1] - h[1], tip[0] - h[0])) % 360
        t1, t2 = sorted((closed % 360, opened))
        if t2 - t1 > 180:
            t1, t2 = t2, t1 + 360
        self.ax.add_patch(
            Arc(
                h,
                2 * w * S,
                2 * w * S,
                theta1=t1,
                theta2=t2,
                lw=0.35,
                color=c,
                ls=(0, (3, 2)),
                zorder=5,
            )
        )

    def tag(self, x, y, label, sub=None, off=(0, 0)):
        p = P(x, y)
        self.ax.add_patch(Circle(p, 2.5, fc="white", ec=INK, lw=0.5, zorder=9))
        self.text(p[0], p[1], label, 5.5, weight="bold", z=10)
        if sub:
            self.text(p[0] + off[0], p[1] + off[1], sub, 4.8, z=10)

    def room_labels(self, pos):
        for r in ROOMS:
            p = P(*pos[r["id"]])
            self.text(p[0], p[1] + 4.5, r["name"].upper(), 6.5, weight="bold")
            self.text(p[0], p[1] - 0.5, f"{area(r['poly']):.2f} m²", 6.5)
            self.text(p[0], p[1] - 4.5, f"clear height {mm(CEIL)}", 5.5, c=GREY)
        p = P((BALCONY[0] + BALCONY[1]) / 2, 7.60)
        self.text(p[0], p[1] + 3, "BALCONY", 6.5, weight="bold")
        self.text(
            p[0], p[1] - 2, f"{(BALCONY[1] - BALCONY[0]) * (BALCONY[3] - BALCONY[2]):.2f} m²", 6.5
        )

    def scale_bar(self, x, y):
        for i in range(4):
            self.ax.add_patch(
                Rectangle(
                    (x + i * 0.5 * S, y),
                    0.5 * S,
                    1.6,
                    fc="black" if i % 2 == 0 else "white",
                    ec=INK,
                    lw=0.5,
                    zorder=6,
                )
            )
        for i in (0, 2, 4):
            self.text(x + i * 0.5 * S, y - 2.6, str(i // 2) + (" m" if i == 4 else ""), 5.5)
        self.text(x - 2, y + 0.8, "1:40", 6, ha="right", weight="bold")

    def north(self, x, y):
        ang = math.radians(FLAT["orientation"]["north_deg"])
        d = (math.cos(ang), math.sin(ang))
        n = (-d[1], d[0])
        tip = (x + 8 * d[0], y + 8 * d[1])
        base = (x - 6 * d[0], y - 6 * d[1])
        self.ax.add_patch(Circle((x, y), 10, fc="white", ec=INK, lw=0.5, zorder=6))
        wing = [
            (base[0] + 3.5 * n[0], base[1] + 3.5 * n[1]),
            (base[0] - 3.5 * n[0], base[1] - 3.5 * n[1]),
        ]
        self.ax.add_patch(Polygon([tip, *wing], fc=INK, ec=INK, zorder=7))
        self.text(x + 14 * d[0], y + 14 * d[1], "N", 8, weight="bold")

    # -- right-hand panel ---------------------------------------------------------------------------
    def title_block(self, sheet_title, sheet_no):
        x0, x1, y0 = PANEL_X, PAGE_W - 12, 12
        self.ax.add_patch(Rectangle((x0, y0), x1 - x0, 30, fc="white", ec=INK, lw=0.8, zorder=2))
        self.line((x0, y0 + 14), (x1, y0 + 14), lw=0.5)
        self.line((x1 - 40, y0), (x1 - 40, y0 + 14), lw=0.5)
        self.text(
            x0 + 3, y0 + 25, "FLAT 19, BUILDING 18, WISZĄCE OGRODY", 9, ha="left", weight="bold"
        )
        self.text(
            x0 + 3, y0 + 19.2, "ul. Przytulna 1, Gdańsk · 2nd floor (II piętro)", 6.5, ha="left"
        )
        self.text(x0 + 3, y0 + 9, sheet_title, 8.5, ha="left", weight="bold")
        self.text(
            x0 + 3,
            y0 + 4,
            "Source: developer's installation plan (DA-2a), 56.68 pt/m",
            5.5,
            ha="left",
            c=GREY,
        )
        self.text(x1 - 20, y0 + 9, f"Sheet {sheet_no}/3", 8, weight="bold")
        self.text(x1 - 20, y0 + 4, "A3 · 1:40 · 2026-10-02", 5.5, c=GREY)

    def table(self, x, y, cols, rows, title, size=5.6, row_h=3.9):
        """cols: [(header, width_mm, align)]. Draws downward from y, returns the y below the table."""
        width = sum(c[1] for c in cols)
        self.text(x, y, title, 7.5, ha="left", weight="bold")
        y -= 4.5
        self.line((x, y + 2.4), (x + width, y + 2.4), lw=0.6)
        cx = x
        for h, w, al in cols:
            self.text(
                cx + (0.8 if al == "left" else w - 0.8), y, h, size, ha=al, weight="bold", c=GREY
            )
            cx += w
        y -= 1.4
        self.line((x, y), (x + width, y), lw=0.4)
        for row in rows:
            y -= row_h
            cx = x
            for i, ((_, w, al), cell) in enumerate(zip(cols, row, strict=True)):
                self.text(
                    cx + (0.8 if al == "left" else w - 0.8),
                    y + 0.2,
                    str(cell),
                    size,
                    ha=al,
                    weight="bold" if i == 0 else "normal",
                )
                cx += w
        self.line((x, y - row_h / 2), (x + width, y - row_h / 2), lw=0.4)
        return y - row_h * 1.4

    def save(self, pdf, png):
        pdf.savefig(self.fig)
        self.fig.savefig(png, dpi=150)
        plt.close(self.fig)


# ===================================================================================================
def sheet_dimensions():
    sh = Sheet()
    sh.architecture()
    sh.room_labels({"living_kitchen": (2.2, 4.1), "bedroom": (5.6, 5.0), "bathroom": (6.4, 1.7)})

    w = {k: v["rect"] for k, v in WALLS.items()}
    south, east, top, west = (
        w["W_corridor_S"],
        w["W_party_east"],
        w["W_ext_bedroom_N"],
        w["W_party_west"],
    )
    # external chains: detail, then overall
    bath_w = w["P_bath_W"]
    sh.chain(
        [west[0], 0, 2.904, 3.956, bath_w[0], bath_w[1], 6.994, east[1]],
        south[2] - 0.45,
        ref=south[2],
    )
    sh.chain([west[0], east[1]], south[2] - 0.85, ref=south[2] - 0.45)
    sh.chain([south[2], 0, 2.99, 3.103, 7.841, top[3]], east[1] + 0.5, False, ref=east[1])
    sh.chain([south[2], top[3]], east[1] + 0.8, False, ref=east[1] + 0.5)
    sh.chain([BALCONY[0], 3.793, 4.153, 4.825, 6.327, 6.994, top[1]], top[3] + 0.45, ref=top[3])
    sh.chain([BALCONY[0], top[1]], top[3] + 0.85, ref=top[3] + 0.45)
    sh.chain([south[2], 0, 0.715, 6.295, 6.722, BALCONY[3]], west[0] - 0.5, False, ref=west[0])
    sh.chain([south[2], BALCONY[3]], west[0] - 0.95, False, ref=west[0] - 0.5)
    # clear room dimensions
    sh.chain([0, 0.552, 3.155, 4.054], 6.0, ref=6.295)
    sh.chain([0, 4.054], 3.55, ref=3.9)
    sh.chain([0.61, 5.155], 2.45, ref=2.2)
    sh.chain([0.715, 6.295], 1.05, False, ref=0.7)
    sh.chain([2.99, 6.295], 3.55, False, ref=3.2)
    sh.chain([3.103, 6.658, 7.558, 7.841], 4.153 + 0.3, False, ref=4.153)
    sh.chain([4.153, 4.203, 5.102, 6.994], 3.103 + 0.3, ref=3.103)
    sh.chain([4.153, 6.994], 5.9, ref=5.6)
    sh.chain([3.103, 7.841], 5.0, False, ref=4.7)
    sh.chain([5.293, 6.994], 2.4, ref=2.0)
    sh.chain([0.311, 2.99], 5.45, False, ref=5.3)
    sh.chain([0, 1.041, 1.941, 2.99], 4.85, False, ref=5.155)
    sh.chain([6.129, 6.994], 0.5, ref=0.311)
    sh.chain([0, 0.61], 0.9, ref=0.715)
    sh.chain([BALCONY[2], BALCONY[3]], 3.5, False, ref=BALCONY[1])

    by_id = {o["id"]: o for o in OPENINGS}
    for oid, (x, y, off) in {
        "O_entrance": (3.43, -0.119, (0, -6.5)),
        "O_bedroom_door": (4.65, 3.05, (0, -6.5)),
        "O_bathroom_door": (5.224, 1.49, (9.5, 0)),
        "O_bedroom_balcony": (3.973, 7.108, (-10.5, 0)),
        "O_living_balcony": (1.85, 6.508, (0, 6.5)),
        "O_bedroom_window": (5.576, 8.027, (0, 6.5)),
    }.items():
        o = by_id[oid]
        a, b, *_ = opening_geometry(o)
        head, ha = opening_height(o)
        sill, sa = opening_sill(o)
        star = "*" if ha or sa else ""
        sub = f"{mm(b - a)}×{mm(head - sill)}{star}" + (f"\nsill {mm(sill)}{star}" if sill else "")
        sh.tag(x, y, TAGS[oid], sub, off)

    sh.title_block("TECHNICAL PLAN · DIMENSIONS", 1)
    sh.north(PANEL_X + 150, 273)
    sh.scale_bar(PANEL_X + 8, 271)
    sh.text(
        PANEL_X,
        262,
        "All dimensions in mm, rounded to 10. Measured from the plan's vectors, ±20 mm.",
        5.5,
        ha="left",
        c=GREY,
    )
    sh.text(
        PANEL_X,
        258.6,
        "* = not printed on the plan, assumed (see the list below). Room dimensions are clear.",
        5.5,
        ha="left",
        c=GREY,
    )

    def val(v, assumed):
        return f"{mm(v)}{'*' if assumed else ''}"

    rows = []
    for o in OPENINGS:
        a, b, *_ = opening_geometry(o)
        head, ha = opening_height(o)
        sill, sa = opening_sill(o)
        rows.append(
            (
                TAGS[o["id"]],
                o["id"][2:].replace("_", " "),
                mm(b - a),
                val(head - sill, ha or sa),
                val(sill, sa),
                val(head, ha),
            )
        )
    cols = [("Tag", 11, "left"), ("Opening", 48, "left")] + [
        (h, 22, "right") for h in ("Width", "Height", "Sill", "Head")
    ]
    y = sh.table(PANEL_X, 250, cols, sorted(rows), "Openings")
    rows = []
    for k, v in WALLS.items():
        a, b, c0, d = v["rect"]
        rows.append(
            (k.replace("_", " "), v["type"], mm(min(b - a, d - c0)), mm(max(b - a, d - c0)))
        )
    cols = [
        ("Wall", 70, "left"),
        ("Type", 38, "left"),
        ("Thickness", 25, "right"),
        ("Length", 25, "right"),
    ]
    y = sh.table(PANEL_X, y, cols, rows, "Walls (shafts hatched)")
    rows = [(r["name"], f"{area(r['poly']):.2f}", mm(CEIL), "finished floor ±0") for r in ROOMS]
    bw, bd = BALCONY[1] - BALCONY[0], BALCONY[3] - BALCONY[2]
    rows.append(("Balcony", f"{bw * bd:.2f}", "open", f"{mm(H['balcony_floor_offset']['value'])}*"))
    total = sum(area(r["poly"]) for r in ROOMS)
    rows.append(("Total (rooms, not the usable area)", f"{total:.2f}", "", ""))
    cols = [
        ("Room", 64, "left"),
        ("Area m²", 24, "right"),
        ("Clear height", 22, "right"),
        ("Floor level", 36, "right"),
    ]
    y = sh.table(PANEL_X, y, cols, rows, "Rooms")
    sh.text(PANEL_X, y + 1, "Assumed, to confirm", 7.5, ha="left", weight="bold")
    for i, (k, v) in enumerate((k, v) for k, v in H.items() if v["assumed"]):
        sh.text(
            PANEL_X,
            y - 3.2 - i * 3.6,
            f"* {k.replace('_', ' ')}: {v['value'] * 1000:.0f} mm. {v['note']}",
            5.0,
            ha="left",
        )
    return sh


# ===================================================================================================
# fixtures drawn inside furniture footprints, and wall symbols
def circ(sh, cx, cy, r, fc="none", lw=0.35, ls="-", z=7):
    sh.ax.add_patch(Circle(P(cx, cy), r * S, fc=fc, ec=INK, lw=lw, ls=ls, zorder=z))


def ell(sh, cx, cy, w, h, lw=0.35, z=7):
    sh.ax.add_patch(Ellipse(P(cx, cy), w * S, h * S, fc="white", ec=INK, lw=lw, zorder=z))


def seg(sh, x0, y0, x1, y1, lw=0.35, ls="-", c=INK, z=7):
    sh.line(P(x0, y0), P(x1, y1), lw=lw, c=c, ls=ls, z=z)


def fixtures(sh, f):
    """Plan symbols for the kitchen, bathroom and bedroom items that carry fixtures."""
    it = {i["id"]: i for i in FURN["items"]}
    sink_y = it["kitchen_base_west"]["params"]["sink_at"]
    sh.box(0.1, 0.5, sink_y - 0.23, sink_y + 0.23, fc="white", lw=0.35, z=7)
    circ(sh, 0.3, sink_y, 0.03)
    seg(sh, 0.06, sink_y, 0.1, sink_y)
    hx = it["kitchen_base_south"]["params"]["hob_at"]
    sh.box(hx - 0.29, hx + 0.29, 0.05, 0.55, lw=0.35, z=7)
    for dx in (-0.14, 0.14):
        for dy in (0.17, 0.43):
            circ(sh, hx + dx, dy, 0.085)
    fx0, fx1, fy0, fy1 = f["fridge"]
    seg(sh, fx0, fy0, fx1, fy1)
    seg(sh, fx0, fy1, fx1, fy0)
    dw = it["kitchen_base_south"]["params"]["dishwasher"]
    sh.box(dw[0], dw[1], 0.02, 0.58, lw=0.35, ls=(0, (3, 2)), z=7)
    seg(sh, dw[0], 0.02, dw[1], 0.58, lw=0.25, ls=(0, (3, 2)))
    wx0, wx1, wy0, wy1 = f["wc"]
    sh.box(wx0, wx1, wy0, wy0 + 0.17, fc="white", lw=0.35, z=7)
    ell(sh, (wx0 + wx1) / 2, wy0 + 0.17 + 0.18, wx1 - wx0 - 0.04, 0.36)
    bx0, bx1, _, _ = f["bath_counter"]
    ell(sh, bx0 + 0.3, it["bath_counter"]["params"]["basin_at"], 0.46, 0.4)
    wmx0, wmx1, wmy0, wmy1 = f["washing_machine"]
    circ(sh, (wmx0 + wmx1) / 2, (wmy0 + wmy1) / 2, 0.22)
    circ(sh, (wmx0 + wmx1) / 2, (wmy0 + wmy1) / 2, 0.15, lw=0.25)
    shower = it["shower"]["params"]
    seg(sh, shower["glass_from_x"], f["shower"][2], shower["glass_from_x"], f["shower"][3], lw=0.8)
    hx_, hy_ = shower["head_at"]
    circ(sh, hx_, hy_, 0.12, lw=0.35)
    circ(sh, hx_, hy_, 0.05, lw=0.25)
    # bed: pillows at the head (the bed faces -x, its head is against the east wall)
    b0, b1, y0, y1 = f["bed"]
    yc = (y0 + y1) / 2
    for lo, hi in ((y0 + 0.08, yc - 0.04), (yc + 0.04, y1 - 0.08)):
        sh.box(b1 - 0.4, b1 - 0.08, lo, hi, fc="white", lw=0.3, z=7)
    seg(sh, b0 + 0.55, y0, b0 + 0.55, y1, lw=0.3)
    # sofa: back rest and seat split
    s0, s1, sy0, sy1 = f["sofa"]
    seg(sh, s0 + 0.25, sy0, s0 + 0.25, sy1, lw=0.3)
    seg(sh, s0 + 0.25, (sy0 + sy1) / 2, s1, (sy0 + sy1) / 2, lw=0.3)
    # TV wall: screen
    t0, t1, ty0, ty1 = f["tv"]
    seg(sh, (t0 + t1) / 2, ty0, (t0 + t1) / 2, ty1, lw=1.1)


SHORT = {
    "kitchen_base_west": "SINK",
    "kitchen_base_south": "HOB",
    "fridge": "FR",
    "dishwasher": "DW",
    "wc": "WC",
    "washing_machine": "WM",
    "bath_counter": "BASIN",
}


def symbol(sh, kind, c, f, proposed=False):
    """Wall symbol centred at paper point c; f = unit vector pointing from the wall into the room."""
    ls = (0, (2, 1.3)) if proposed else "-"
    n = (-f[1], f[0])
    wall = (c[0] - f[0] * 1.9, c[1] - f[1] * 1.9)

    def ring(p, r, fc="white"):
        sh.ax.add_patch(Circle(p, r, fc=fc, ec=INK, lw=0.5, ls=ls, zorder=12))

    if kind in ("socket", "socket2"):
        centres = (
            [c]
            if kind == "socket"
            else [(c[0] - n[0] * 1.2, c[1] - n[1] * 1.2), (c[0] + n[0] * 1.2, c[1] + n[1] * 1.2)]
        )
        for p in centres:
            sh.line(
                (p[0] - f[0] * 1.3, p[1] - f[1] * 1.3),
                (p[0] - f[0] * 1.9, p[1] - f[1] * 1.9),
                lw=0.5,
                z=12,
            )
            ring(p, 1.0 if kind == "socket2" else 1.3)
    elif kind == "socket400":
        ring(c, 1.5, fc=INK)
    elif kind in ("data", "intercom"):
        sh.ax.add_patch(
            Rectangle(
                (c[0] - 1.6, c[1] - 1.6), 3.2, 3.2, fc="white", ec=INK, lw=0.5, ls=ls, zorder=12
            )
        )
        sh.text(c[0], c[1], "TV" if kind == "data" else "IC", 3.4, z=13)
    elif kind == "switch":
        ring(c, 1.1)
        sh.line(c, (c[0] + (f[0] + n[0]) * 2.4, c[1] + (f[1] + n[1]) * 2.4), lw=0.5, z=12)
    elif kind == "water":
        sh.ax.add_patch(
            Polygon(
                [(c[0], c[1] + 2.0), (c[0] + 2.0, c[1]), (c[0], c[1] - 2.0), (c[0] - 2.0, c[1])],
                fc="white",
                ec=INK,
                lw=0.5,
                ls=ls,
                zorder=12,
            )
        )
        sh.text(c[0], c[1], "W", 3.4, z=13)
    elif kind == "light":
        ring(c, 1.5)
        for a in (0, 45, 90, 135):
            d = (math.cos(math.radians(a)) * 2.2, math.sin(math.radians(a)) * 2.2)
            sh.line((c[0] - d[0], c[1] - d[1]), (c[0] + d[0], c[1] + d[1]), lw=0.4, z=13)
    del wall


FACE = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
KINDS = {
    "socket": "Socket 230 V",
    "socket2": "Double socket 230 V",
    "socket400": "Socket 400 V",
    "data": "TV / SAT / data + socket",
    "water": "Water supply and drain",
    "switch": "Light switches A, B",
    "intercom": "Intercom",
    "light": "Wall light outlet",
}


def wall_points(sh):
    """Draw every point of data/electrical.json, spreading points that sit closer than 0.2 m."""
    placed = []
    for p in ELEC:
        f = FACE[p["face"]]
        along = p["at"][1] if f[0] else p["at"][0]
        wall = p["at"][0] if f[0] else p["at"][1]
        k = sum(
            1
            for (fw, w, a) in placed
            if fw == p["face"] and abs(w - wall) < 1e-6 and abs(a - along) < 0.2
        )
        placed.append((p["face"], wall, along))
        base = P(*p["at"])
        n = (-f[1], f[0])
        c = (base[0] + f[0] * 2.2 + n[0] * 3.8 * k, base[1] + f[1] * 2.2 + n[1] * 3.8 * k)
        symbol(sh, p["kind"], c, f, p["source"] == "proposed")
        lab = (c[0] + f[0] * 4.2, c[1] + f[1] * 4.2)
        sh.text(lab[0], lab[1], p["id"], 4.6, weight="bold", z=13)


def sheet_fitout():
    sh = Sheet()
    sh.architecture(tone=0.55)
    f = {i["id"]: i["footprint"] for i in FURN["items"]}
    numbered, seen = [], {}
    for it in FURN["items"]:
        if it["cat"] == "decor":
            continue
        x0, x1, y0, y1 = it["footprint"]
        if it["cat"] == "rug":
            sh.box(x0, x1, y0, y1, ec=GREY, lw=0.5, ls=(0, (6, 3)), z=2)
            continue
        if it["id"] in ("footrest", "balcony_table"):
            circ(sh, (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, fc="white", lw=0.5, z=5)
        elif it["z"][0] >= 0.3:
            sh.box(x0, x1, y0, y1, ec=INK, lw=0.5, ls=(0, (3, 2)), z=6)
        else:
            sh.box(x0, x1, y0, y1, fc="white", ec=INK, lw=0.5, z=5)
        if min(x1 - x0, y1 - y0) >= 0.08 or it["cat"] in ("tv", "wall"):
            seen.setdefault(tuple(it["footprint"]), []).append(it)
    for n, group in enumerate(seen.values(), 1):
        numbered.append(group[0])
        for k, it in enumerate(group):
            it["_n"] = f"{n}{chr(97 + k)}" if len(group) > 1 else n
        group[0]["_tag"] = str(n)
    fixtures(sh, f)
    for it in numbered:
        x0, x1, y0, y1 = it["footprint"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if it["z"][0] >= 0.3:  # hanging items sit over base units: tag them at the far end
            if x1 - x0 >= y1 - y0:
                cx = x1 - 0.12
            else:
                cy = y1 - 0.12
        if it["id"] == "shower":
            cx = 5.65
        sh.tag(cx, cy, it["_tag"])

    sh.chain([f["fridge"][3], f["peninsula"][2]], 0.9, False, ref=0.9, size=5)
    sh.chain([f["peninsula"][1], 4.054], 2.4, ref=2.55, size=5)
    sh.chain([f["bed"][3], f["desk"][2]], 5.1, False, ref=4.9, size=5)
    sh.chain([f["bed_wardrobe"][3], f["bed"][2]], 6.2, False, ref=6.0, size=5)
    sh.chain([4.153, f["bed"][0]], 5.25, ref=5.0, size=5)
    sh.chain([f["sofa"][1], f["tv"][0]], 4.0, ref=4.1, size=5)
    sh.chain([f["wc"][1], f["bath_counter"][0]], 0.55, ref=0.4, size=5)

    sh.title_block("FIT-OUT PLAN · FURNITURE AND CLEARANCES", 2)
    sh.north(PANEL_X + 150, 273)
    sh.scale_bar(PANEL_X + 8, 271)
    sh.text(
        PANEL_X,
        262,
        "Sizes W × D × H in mm. X, Y = south-west corner of the footprint, from the inner SW corner of the living room.",
        5.0,
        ha="left",
        c=GREY,
    )
    sh.text(
        PANEL_X,
        258.6,
        "Dashed outline = wall-mounted or hanging. Dashed grey = rug. Dimensions are clear distances between faces.",
        5.0,
        ha="left",
        c=GREY,
    )
    rows = []
    for it in FURN["items"]:
        if "_n" not in it:
            continue
        x0, x1, y0, y1 = it["footprint"]
        name = it.get("label") or it["id"].replace("_", " ")
        size = f"{mm(x1 - x0)} × {mm(y1 - y0)} × {mm(it['z'][1] - it['z'][0])}"
        rows.append((it["_n"], name[:30], size, f"{mm(x0)}, {mm(y0)}", f"{mm(it['z'][0])}"))
    cols = [
        ("#", 8, "left"),
        ("Item", 44, "left"),
        ("W × D × H", 36, "right"),
        ("X, Y", 24, "right"),
        ("Bottom", 18, "right"),
    ]
    sh.table(PANEL_X, 250, cols, rows, "Furniture", size=5.0, row_h=3.3)
    return sh


def sheet_services():
    sh = Sheet()
    sh.architecture(tone=0.55)
    for it in FURN["items"]:
        if it["cat"] in ("decor", "rug") or it["id"] in ("footrest", "balcony_table"):
            continue
        x0, x1, y0, y1 = it["footprint"]
        hang = it["z"][0] >= 0.3
        sh.box(x0, x1, y0, y1, ec="#9a9a9a", lw=0.3, ls=(0, (3, 2)) if hang else "-", z=2)
    fx = FLAT["fixtures_reference"]
    for rname in ("radiator_living", "radiator_bedroom"):
        r = rect_m(fx[rname]["rect_pt"])
        sh.box(*r, fc="white", ec=INK, lw=0.5, hatch="||||", z=6)
        c = P((r[0] + r[1]) / 2, (r[2] + r[3]) / 2)
        sh.text(c[0] + 8.5, c[1] - 3.8, "RAD", 4.4, weight="bold")
    sh.box(*rect_m(fx["fuse_box_RM"]["rect_pt"]), fc=INK, ec=INK, lw=0.5, z=6)
    c = P(4.94, 0.0)
    sh.text(c[0], c[1] + 4.6, "RM", 4.8, weight="bold")
    towel = {i["id"]: i["footprint"] for i in FURN["items"]}["towel_rail"]
    sh.box(*towel, fc="white", ec=INK, lw=0.5, hatch="--", z=6)

    wall_points(sh)

    # ceiling: light outlets and the fixtures hung on them
    out = {
        k: (mx(v["pt"][0]), my(v["pt"][1])) for k, v in OUTLETS.items() if v["kind"] == "ceiling"
    }
    for fixture in LIGHTS["fixtures"]:
        t = fixture["type"]
        if t == "led_strip":
            (ax_, _), (_, by) = out[fixture["outlets"][0]], out[fixture["outlets"][1]]
            pts = [P(ax_, fixture["start_y"]), P(ax_, by), P(fixture["end_x"], by)]
            for a, b in itertools.pairwise(pts):
                sh.line(a, b, lw=1.6, c=GREY, ls=(0, (6, 1.5, 1, 1.5)), z=4)
        elif t == "globe_pendants":
            for at in fixture["at"]:
                circ(sh, at[0], at[1], 0.09, lw=0.5, ls=(0, (2, 1.5)), z=10)
        elif t in ("lantern", "flush_disc"):
            x, y = out[fixture["outlet"]]
            circ(
                sh, x, y, fixture["radius"], lw=0.4, ls=(0, (4, 2)) if t == "lantern" else "-", z=4
            )
    for name, (x, y) in out.items():
        p = P(x, y)
        sh.ax.add_patch(Circle(p, 2.0, fc="white", ec=INK, lw=0.6, zorder=10))
        sh.line((p[0] - 1.4, p[1] - 1.4), (p[0] + 1.4, p[1] + 1.4), lw=0.5, z=11)
        sh.line((p[0] - 1.4, p[1] + 1.4), (p[0] + 1.4, p[1] - 1.4), lw=0.5, z=11)
        sh.text(p[0] + 3.6, p[1] + 2.8, name, 5.2, weight="bold", z=12)

    # positions along the walls
    sh.chain([0.715, 1.0, 1.64, 1.82, 3.5, 6.0, 6.295], -0.5, False, ref=-0.203, size=5)
    sh.chain([0.61, 0.9, 1.32, 2.3, 2.754, 2.79], -0.45, ref=-0.238, size=5)
    sh.chain([5.293, 5.72, 6.129], -0.45, ref=-0.238, size=5)
    sh.chain([0, 0.5, 0.66, 1.64, 2.99, 5.25, 7.05, 7.841], 7.198 + 0.45, False, ref=7.198, size=5)
    sh.chain([2.99, 5.3, 6.295], 3.55, False, ref=4.054, size=5)

    sh.title_block("SERVICES · SOCKETS, SWITCHES, WATER, LIGHTS", 3)
    sh.north(PANEL_X + 150, 273)
    sh.scale_bar(PANEL_X + 8, 271)
    sh.text(
        PANEL_X,
        262,
        "X, Y from the inner SW corner of the living room, in mm. h = height above the finished floor.",
        5.0,
        ha="left",
        c=GREY,
    )
    sh.text(
        PANEL_X,
        258.6,
        "* = height not printed on the plan, set by convention. PROPOSED = not on the developer's plan, to confirm.",
        5.0,
        ha="left",
        c=GREY,
    )
    rows = []
    for p in ELEC:
        rows.append(
            (
                p["id"],
                KINDS[p["kind"]],
                p["room"],
                f"{mm(p['at'][0])}, {mm(p['at'][1])}",
                f"{mm(p['h'])}{'*' if p['h_assumed'] else ''}",
                p["source"].upper() if p["source"] == "proposed" else "plan",
            )
        )
    for name, v in OUTLETS.items():
        if v["kind"] == "ceiling":
            rows.append(
                (
                    name,
                    "Ceiling light outlet",
                    v["room"].split(",")[0],
                    f"{mm(mx(v['pt'][0]))}, {mm(my(v['pt'][1]))}",
                    mm(CEIL),
                    "plan",
                )
            )
    cols = [
        ("ID", 9, "left"),
        ("Point", 42, "left"),
        ("Room", 22, "left"),
        ("X, Y", 26, "right"),
        ("h", 14, "right"),
        ("Source", 18, "right"),
    ]
    y = sh.table(PANEL_X, 250, cols, rows, "Points", size=4.9, row_h=3.15)
    sh.text(PANEL_X, y + 1, "Notes", 7.5, ha="left", weight="bold")
    notes = [
        f"{p['id']}: {p['note']}" for p in ELEC if p["source"] == "proposed" or len(p["note"]) > 45
    ]
    notes += [
        "Dining pendants (dashed circles) are not on an outlet: they need a cable from outlet B. LED profile runs A, then B.",
        "Kitchen shaft: sewer stack, ventilation and the hood duct. Bath shaft: behind the washing machine and basin.",
        "Radiators (hatched) are fixed by the developer. Only the points on the plan are measured; other switches are not on it.",
    ]
    i = 0
    for note in notes:
        for k, line in enumerate(textwrap.wrap(note, 118)):
            sh.text(PANEL_X, y - 3.2 - i * 3.1, ("   " if k else "") + line, 4.7, ha="left")
            i += 1

    # symbol key
    kx, ky = PANEL_X + 100, 104
    sh.text(kx, ky + 1, "Key", 7.5, ha="left", weight="bold")
    for i, (kind, label) in enumerate(
        (
            ("socket", "socket 230 V"),
            ("socket2", "double socket"),
            ("socket400", "socket 400 V"),
            ("data", "TV / SAT / data"),
            ("switch", "light switch"),
            ("intercom", "intercom"),
            ("water", "water + drain"),
            ("light", "wall light"),
        )
    ):
        c = (kx + 3 + (i // 4) * 30, ky - 6 - (i % 4) * 5.5)
        symbol(sh, kind, c, (0, 1))
        sh.text(c[0] + 4.5, c[1], label, 4.6, ha="left")
    c = (kx + 3, ky - 29)
    symbol(sh, "socket", c, (0, 1), proposed=True)
    sh.text(c[0] + 4.5, c[1], "dashed = proposed (not on the plan)", 4.6, ha="left")
    return sh


def main():
    out = ROOT / "renders"
    out.mkdir(exist_ok=True)
    with PdfPages(out / "technical_plan.pdf") as pdf:
        sheet_dimensions().save(pdf, out / "technical_plan_dimensions.png")
        sheet_fitout().save(pdf, out / "technical_plan_fitout.png")
        sheet_services().save(pdf, out / "technical_plan_services.png")
    print("Wrote", out / "technical_plan.pdf")


if __name__ == "__main__":
    main()
