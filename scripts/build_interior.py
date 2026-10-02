"""Furnish the shell into a photoreal interior: materials, finishes, doors, furniture, decor, lights, cameras.

    blender --background --factory-startup --python scripts/build_interior.py

Needs blender/apartment_shell.blend (make shell) and assets/ (make assets). Writes blender/apartment.blend;
render it with scripts/render.py. Everything is rebuilt from data/*.json on every run.
"""

import datetime
import json
import math
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import itertools

import build_shell as shell  # noqa: E402
import furniture as F  # noqa: E402
import materials  # noqa: E402
import modes  # noqa: E402

ROOT = shell.ROOT
DATA = shell.DATA
FURN = json.loads((ROOT / "data" / "furniture.json").read_text())
DECOR = json.loads((ROOT / "data" / "decor.json").read_text())
CAMS = json.loads((ROOT / "data" / "cameras.json").read_text())["cameras"]
SITE = json.loads((ROOT / "data" / "site.json").read_text())
LIGHTING = json.loads((ROOT / "data" / "lighting.json").read_text())
PH = ROOT / "assets" / "polyhaven"
CEIL = shell.CEIL
X, Y = shell.X, shell.Y

HDRI = "park_parking_4k.hdr"
HDRI_CLAMP = (
    6.0  # radiance above this is the sun disc; it is cut from the HDRI and given to the Sun lamp
)
DOOR_OPEN_DEG = {"O_bedroom_door": 75, "O_bathroom_door": 60}

S = {}  # collections


# ---------------------------------------------------------------- helpers


def opening_geometry(o):
    w = next(w for w in DATA["walls"] if w["id"] == o["wall"])
    wb = shell.rect_m(w["rect_pt"])
    along_x = o["axis"] == "x"
    a, b = (
        sorted((X(o["span_pt"][0]), X(o["span_pt"][1])))
        if along_x
        else sorted((Y(o["span_pt"][0]), Y(o["span_pt"][1])))
    )
    sill = shell.H[o["sill"]] if "sill" in o else o.get("sill_m", 0.0)
    head = shell.H[o["head"]]
    mid = (wb[2] + wb[3]) / 2 if along_x else (wb[0] + wb[1]) / 2
    return wb, along_x, a, b, sill, head, mid


def solar_position(lat, lon, when):
    """Sun azimuth (degrees clockwise from north) and elevation for a moment, low-precision almanac formulas
    (good to well under a degree, plenty for lighting)."""
    n = (when - datetime.datetime(2000, 1, 1, 12, tzinfo=datetime.UTC)).total_seconds() / 86400
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    ha = math.radians(gmst * 15 + lon) - ra
    la = math.radians(lat)
    el = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(la) - math.sin(la) * math.cos(ha))
    return math.degrees(az) % 360, math.degrees(el)


def sun_in_plan():
    """(azimuth in the Blender frame, degrees counter-clockwise from +X; elevation) for site.json's date_time."""
    o = DATA["orientation"]
    when = datetime.datetime.fromisoformat(SITE["date_time"])
    az, el = solar_position(o["latitude"], o["longitude"], when)
    return (o["north_deg"] - az) % 360, el


def room_poly(room_id):
    r = next(r for r in DATA["rooms"] if r["id"] == room_id)
    return [(X(px), Y(py)) for px, py in r["polygon_pt"]]


def signed_area(poly):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) / 2


def wall_runs(room_id, skip_openings=True):
    """Yield (axis, fixed, s0, s1, inward_sign) for each wall-face segment of a room, minus floor-level openings.

    axis 'x' means the face runs along X at y = fixed and the room lies toward inward_sign * Y.
    """
    poly = room_poly(room_id)
    ccw = signed_area(poly) > 0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if abs(y1 - y2) < 1e-6:
            axis, fixed, s0, s1 = "x", y1, min(x1, x2), max(x1, x2)
            inward = (1 if x2 > x1 else -1) * (
                1 if ccw else -1
            )  # left of the direction of travel for CCW
        else:
            axis, fixed, s0, s1 = "y", x1, min(y1, y2), max(y1, y2)
            inward = (-1 if y2 > y1 else 1) * (1 if ccw else -1)
        cuts = []
        for o in DATA["openings"] if skip_openings else []:
            wb, along_x, a, b, sill, head, mid = opening_geometry(o)
            if along_x != (axis == "x") or sill > 0.01:
                continue
            lo, hi = (wb[2], wb[3]) if along_x else (wb[0], wb[1])
            if lo - 0.02 <= fixed <= hi + 0.02:
                cuts.append((a, b))
        segs = [(s0, s1)]
        for a, b in cuts:
            segs = [
                piece
                for s, e in segs
                for piece in ((s, min(e, a)), (max(s, b), e))
                if piece[1] - piece[0] > 0.005
            ]
        for s, e in segs:
            yield axis, fixed, s, e, inward


def slab_on_face(name, axis, fixed, s0, s1, inward, thick, z0, z1, mat, coll):
    p0, p1 = sorted((fixed, fixed + inward * thick))
    if axis == "x":
        return _in(coll, F.box(name, s0, s1, p0, p1, z0, z1, mat, None))
    return _in(coll, F.box(name, p0, p1, s0, s1, z0, z1, mat, None))


def _in(coll, obj):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def set_mat(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---------------------------------------------------------------- architecture


def restyle(L):
    for o in S["walls"].objects:
        set_mat(o, L["wall"])
    floor_mat = {
        "Floor_living_kitchen": "floor_oak",
        "Floor_bedroom": "floor_oak",
        "Floor_bathroom": "bath_floor",
    }
    for o in S["floors"].objects:
        set_mat(o, L[floor_mat[o.name]])
    for o in S["ceilings"].objects:
        set_mat(o, L["ceiling"])
    for o in list(S["openings"].objects):
        if "leaf" in o.name:
            bpy.data.objects.remove(o)
        elif "glass" in o.name:
            set_mat(o, L["glass"])
        else:
            set_mat(o, L["pvc"])
    # Interior door frames are rebuilt in doors(); drop the shell's simple jambs for them
    for oid in ("O_entrance", "O_bedroom_door", "O_bathroom_door"):
        for suffix in ("_jamb_a", "_jamb_b", "_head"):
            ob = bpy.data.objects.get(oid + suffix)
            if ob:
                bpy.data.objects.remove(ob)
    for o in list(bpy.data.collections["Annotations"].objects):
        bpy.data.objects.remove(o)
    ext = {
        "Balcony_Slab": "balcony",
        "Balcony_PrivacyScreen": "facade",
        "Structural_Slab": "balcony",
    }
    for name, key in ext.items():
        set_mat(bpy.data.objects[name], L[key])
    # Seal the top so no light leaks in along wall/ceiling seams
    xs = [v for w in DATA["walls"] for v in shell.rect_m(w["rect_pt"])[:2]]
    ys = [v for w in DATA["walls"] for v in shell.rect_m(w["rect_pt"])[2:]]
    _in(
        S["arch"],
        F.box(
            "Roof_Seal",
            min(xs),
            max(xs),
            min(ys),
            max(ys),
            CEIL + 0.02,
            CEIL + 0.30,
            L["balcony"],
            None,
        ),
    )


def finishes(L):
    c = S["finishes"]
    # Skirting in the oak-floored rooms
    for room in ("living_kitchen", "bedroom"):
        for i, (axis, fixed, s0, s1, inward) in enumerate(wall_runs(room)):
            if (
                axis == "y"
            ):  # the X runs own the corner squares; trimming avoids overlapping volumes
                s0, s1 = s0 + 0.012, s1 - 0.012
            slab_on_face(
                f"Skirting_{room}_{i}",
                axis,
                fixed,
                s0,
                s1,
                inward,
                0.012,
                0.0,
                0.06,
                L["skirting"],
                c,
            )
    # Bathroom: white marble-look tiles on every wall; forest-green hexagons full height on the shower's
    # back wall
    shower = next(it for it in FURN["items"] if it["id"] == "shower")["footprint"]
    for i, (axis, fixed, s0, s1, inward) in enumerate(wall_runs("bathroom")):
        back_wall = axis == "x" and abs(fixed - shower[3]) < 0.02
        mat = L["hex_green"] if back_wall else L[f"bath_wall_{axis}"]
        slab_on_face(f"BathTile_{i}", axis, fixed, s0, s1, inward, 0.008, 0.0, CEIL, mat, c)
    o = next(o for o in DATA["openings"] if o["id"] == "O_bathroom_door")
    wb, along_x, a, b, sill, head, mid = opening_geometry(o)
    slab_on_face("BathTile_header", "y", wb[1], a, b, 1, 0.008, head, CEIL, L["bath_wall_y"], c)
    # Bedroom accent: greige on the headboard wall
    slab_on_face(
        "Accent_bedroom_east",
        "y",
        X(750.4),
        Y(467.1),
        Y(198.6),
        -1,
        0.002,
        0.0,
        CEIL,
        L["wall_accent"],
        c,
    )
    # Stone sill inside the bedroom window
    o = next(o for o in DATA["openings"] if o["id"] == "O_bedroom_window")
    wb, along_x, a, b, sill, head, mid = opening_geometry(o)
    _in(
        c,
        F.box(
            "Sill_bedroom",
            a - 0.03,
            b + 0.03,
            wb[2] - 0.035,
            mid,
            sill - 0.025,
            sill,
            L["sill_stone"],
            None,
            bev=0.003,
        ),
    )
    # Radiators from the developer's plan (positions in data/floorplan.json fixtures_reference)
    radiator(
        "Radiator_living", X(535.0), X(560.0), Y(286.2) - 0.14, Y(286.2) - 0.04, 0.15, 1.05, L, c
    )
    radiator(
        "Radiator_bedroom", X(638.0), X(700.0), Y(198.6) - 0.14, Y(198.6) - 0.04, 0.12, 0.42, L, c
    )


def radiator(name, x0, x1, y0, y1, z0, z1, L, coll):
    _in(coll, F.box(name, x0, x1, y0, y1, z0, z1, L["radiator"], None, bev=0.004))
    k = int((x1 - x0) / 0.05)
    for i in range(1, k):
        x = x0 + (x1 - x0) * i / k
        _in(
            coll,
            F.box(
                f"{name}_rib{i}",
                x - 0.004,
                x + 0.004,
                y0 - 0.003,
                y0,
                z0 + 0.03,
                z1 - 0.03,
                L["radiator"],
                None,
                bev=0.002,
            ),
        )
    _in(
        coll,
        F.box(
            name + "_grille",
            x0 + 0.01,
            x1 - 0.01,
            y0 + 0.01,
            y1 - 0.01,
            z1,
            z1 + 0.003,
            L["plastic_black"],
            None,
        ),
    )
    _in(
        coll,
        F.cyl(
            name + "_valve",
            x1 + 0.03,
            (y0 + y1) / 2,
            z0 - 0.02,
            z0 + 0.06,
            0.015,
            L["chrome"],
            None,
        ),
    )


# ---------------------------------------------------------------- doors


def doors(L):
    c = S["doors"]
    for o in DATA["openings"]:
        if o["kind"] not in ("door", "window_door"):
            continue
        wb, along_x, a, b, sill, head, mid = opening_geometry(o)
        oid = o["id"]
        interior = oid in ("O_entrance", "O_bedroom_door", "O_bathroom_door")
        lining, fw = (0.02, 0.0) if interior else (0.0, 0.06)
        thick_lo, thick_hi = (wb[2], wb[3]) if along_x else (wb[0], wb[1])
        frame_mat = L["door_entrance"] if oid == "O_entrance" else L["door_white"]
        if interior:
            door_frame(oid, along_x, a, b, head, thick_lo, thick_hi, frame_mat, c)
        parts = o.get("parts_pt") or [{"kind": "door", "span": o["span_pt"]}]
        for p in parts:
            s0, s1 = (
                sorted((X(p["span"][0]), X(p["span"][1])))
                if along_x
                else sorted((Y(p["span"][0]), Y(p["span"][1])))
            )
            s0, s1 = max(s0, a + fw + lining), min(s1, b - fw - lining)
            z0, z1 = sill + 0.008, head - (fw or lining) - 0.003
            if p["kind"] == "fixed":
                continue
            glazed = not interior
            mat = L["door_entrance"] if oid == "O_entrance" else L["door_white"]
            if p["kind"] == "door_pair":
                half = (s1 - s0) / 2
                door_leaf(
                    oid + "_leafL", s0, +1, half - 0.002, along_x, mid, z0, z1, o, glazed, mat, L, c
                )
                door_leaf(
                    oid + "_leafR", s1, -1, half - 0.002, along_x, mid, z0, z1, o, glazed, mat, L, c
                )
            else:
                at_start = o["hinge"] in ("west", "south")
                door_leaf(
                    oid + "_leaf",
                    s0 + 0.003 if at_start else s1 - 0.003,
                    1 if at_start else -1,
                    s1 - s0 - 0.006,
                    along_x,
                    mid,
                    z0,
                    z1,
                    o,
                    glazed,
                    mat,
                    L,
                    c,
                )


def door_frame(oid, along_x, a, b, head, lo, hi, mat, coll):
    """Lining across the full wall thickness plus 7 cm architraves on both faces."""
    t, aw, ap = 0.02, 0.07, 0.012

    def bx(name, s0, s1, p0, p1, z0, z1):
        if along_x:
            return _in(coll, F.box(name, s0, s1, p0, p1, z0, z1, mat, None, bev=0.0015))
        return _in(coll, F.box(name, p0, p1, s0, s1, z0, z1, mat, None, bev=0.0015))

    bx(oid + "_lining_a", a, a + t, lo, hi, 0, head - t)
    bx(oid + "_lining_b", b - t, b, lo, hi, 0, head - t)
    bx(oid + "_lining_top", a, b, lo, hi, head - t, head)
    for side, (p0, p1) in (("in", (lo - ap, lo)), ("out", (hi, hi + ap))):
        bx(f"{oid}_arch_{side}_a", a - aw, a, p0, p1, 0, head)
        bx(f"{oid}_arch_{side}_b", b, b + aw, p0, p1, 0, head)
        bx(f"{oid}_arch_{side}_top", a - aw, b + aw, p0, p1, head, head + aw)


def door_leaf(name, hinge_s, direction, length, along_x, mid, z0, z1, o, glazed, mat, L, coll):
    """A leaf built along local +X from its hinge, then rotated open toward the opening's swing direction."""
    t = (
        0.04 if not glazed else 0.06
    )  # glazed leaves sit inside the 7 cm outer frame, faces not coplanar
    root = F.empty(name, coll)
    # Orientation: u = hinge -> latch along the opening; swing rotates the leaf toward swing_dir.
    # The leaf's local +Y is u rotated 90 deg; doors open inward, so the room side is toward swing_dir.
    u = Vector((direction, 0)) if along_x else Vector((0, direction))
    s = Vector(o["swing_dir"])
    inside = 1 if (-u.y * s.x + u.x * s.y) > 0 else -1
    if glazed:
        fw = 0.075
        # Stiles full height, rails between them: no overlapping volumes
        for part, (x0, x1, zz0, zz1) in {
            "l": (0, fw, z0, z1),
            "r": (length - fw, length, z0, z1),
            "b": (fw, length - fw, z0, z0 + fw + 0.04),
            "t": (fw, length - fw, z1 - fw, z1),
        }.items():
            F.box(
                f"{name}_frame_{part}", x0, x1, -t / 2, t / 2, zz0, zz1, L["pvc"], root, bev=0.003
            )
        F.box(
            name + "_glass",
            fw,
            length - fw,
            -0.012,
            0.012,
            z0 + fw + 0.04,
            z1 - fw,
            L["glass"],
            root,
        )
        handle(name, length - 0.04, t / 2, 1.05, L["plastic_white"], root, sides=(inside,))
    else:
        F.box(name + "_slab", 0, length, -t / 2, t / 2, z0, z1, mat, root, bev=0.002)
        handle(name, length - 0.065, t / 2, 1.02, L["black_metal"], root, sides=(-1, 1))
        if o["id"] == "O_entrance":
            F.cyl(name + "_peephole", 0, 0, -0.025, 0.025, 0.008, L["steel"], root).matrix_basis = (
                Matrix.Translation((length / 2, 0, 1.55)) @ Matrix.Rotation(math.pi / 2, 4, "X")
            )
    base = math.atan2(u.y, u.x)
    sign = 1 if (u.x * s.y - u.y * s.x) > 0 else -1
    ang = math.radians(DOOR_OPEN_DEG.get(o["id"], 0))
    root.location = (hinge_s, mid, 0) if along_x else (mid, hinge_s, 0)
    root.rotation_euler.z = base + sign * ang


def handle(name, x, y_face, z, mat, parent, sides=(-1, 1)):
    for sd in sides:
        y = sd * abs(y_face)
        F.cyl(f"{name}_rose{sd}", 0, 0, 0, 0.01, 0.026, mat, parent).matrix_basis = _mx(
            (x, y, z), sd
        )
        F.tube_path(
            f"{name}_lever{sd}",
            [(x, y + sd * 0.01, z), (x, y + sd * 0.055, z), (x - 0.13, y + sd * 0.055, z)],
            0.009,
            mat,
            parent,
        )


def _mx(loc, sd):
    return Matrix.Translation(loc) @ Matrix.Rotation(-sd * math.pi / 2, 4, "X")


# ---------------------------------------------------------------- Poly Haven assets

_PH_CACHE = {}
LOD_KEEP = "_LOD1"


def ph_instance(asset_id, name, coll):
    """Import a Poly Haven model once, then hand out linked copies. Returns an empty whose children are the
    model, re-centred so the empty sits at the model's base centre, front facing -Y."""
    if asset_id not in _PH_CACHE:
        d = PH / "models" / asset_id
        blend = next(d.glob("*.blend"))
        before = set(bpy.data.images)
        with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
            dst.objects = list(src.objects)
        for img in set(bpy.data.images) - before:
            # Append usually rebases '//textures/..' onto the current file; fix up any that it didn't
            if not Path(bpy.path.abspath(img.filepath)).exists():
                img.filepath = str(d / "textures" / Path(img.filepath).name)
        objs = [o for o in dst.objects if o is not None and o.type in ("MESH", "EMPTY", "CURVE")]
        # Poly Haven trees ship LOD0 and LOD1 stacked at one spot: keep LOD1 only (no double geometry, ~90 MB smaller)
        if any(o.name.endswith(LOD_KEEP) for o in objs):
            for o in [
                o for o in objs if re.search(r"_LOD\d+$", o.name) and not o.name.endswith(LOD_KEEP)
            ]:
                objs.remove(o)
                bpy.data.objects.remove(o)
        lib_coll = bpy.data.collections.new("_ph_" + asset_id)
        for o in objs:
            lib_coll.objects.link(o)
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        _PH_CACHE[asset_id] = (objs, Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)), hi - lo)
    objs, base, size = _PH_CACHE[asset_id]
    root = F.empty(name, coll)
    inner = F.empty(name + "_offset", coll)
    inner.parent = root
    inner.location = -base
    mapping = {}
    for o in objs:
        cp = o.copy()  # shares mesh data with the cached original
        coll.objects.link(cp)
        mapping[o] = cp
    for o, cp in mapping.items():
        cp.parent = mapping.get(o.parent, inner)
        if o.parent is None:
            cp.matrix_parent_inverse.identity()
            cp.matrix_basis = o.matrix_world.copy()
    root["asset_size"] = list(size)
    return root


def furniture():
    rooms = {}
    for it in FURN["items"]:
        coll = rooms.get(it["room"]) or shell.collection("Furniture_" + it["room"], S["furniture"])
        rooms[it["room"]] = coll
        kind, _, ref = it["source"].partition(":")
        if kind == "proc":
            root = F.empty(it["id"], coll)
            F.GENERATORS[ref](it, root)
            if ref not in F.WORLD_SPACE:
                F.place(root, it)
                root.location.z = it.get("base_z", 0.0)
        elif kind == "polyhaven":
            root = ph_instance(ref, it["id"], coll)
            x0, x1, y0, y1 = it["footprint"]
            root.location = ((x0 + x1) / 2, (y0 + y1) / 2, it["z"][0])
            root.rotation_euler.z = {"-y": 0, "+y": math.pi, "+x": math.pi / 2, "-x": -math.pi / 2}[
                it["facing"]
            ]


def decor():
    c = S["decor"]
    for i, d in enumerate(DECOR["items"]):
        kind, _, ref = d["asset"].partition(":")
        x, y, z = d["at"]
        if kind == "proc" and ref == "table_lamp":
            F.table_lamp(f"TableLamp_{i}", x, y, z, F.empty(f"Decor_{i}_table_lamp", c))
            continue
        root = ph_instance(ref, f"Decor_{i}_{ref}", c)
        root.location = (x, y, z)
        root.rotation_euler.z = math.radians(d.get("rot", 0))
        root.scale = (d.get("scale", 1.0),) * 3


# ---------------------------------------------------------------- textiles and lights


def curtains(L):
    c = S["textiles"]
    y = Y(286.2) - 0.215  # track in front of the tall radiator
    F_mat = L["sheer"]
    _in(
        c,
        F.box(
            "Curtain_track_living",
            0.05,
            3.95,
            y - 0.012,
            y + 0.012,
            CEIL - 0.03,
            CEIL,
            L["plastic_white"],
            None,
        ),
    )
    for name, x0, x1 in (("Curtain_living_L", 0.05, 0.70), ("Curtain_living_R", 3.15, 3.95)):
        curtain(name, x0, x1, y, 0.015, CEIL - 0.035, F_mat, c)
    # Roman blind, raised, inside the bedroom window reveal
    o = next(o for o in DATA["openings"] if o["id"] == "O_bedroom_window")
    wb, along_x, a, b, sill, head, mid = opening_geometry(o)
    for k in range(3):
        f = _in(
            c,
            F.box(
                f"Blind_bedroom_fold{k}",
                a + 0.03,
                b - 0.03,
                wb[2] + 0.04,
                wb[2] + 0.10,
                head - 0.06 - 0.055 * (k + 1),
                head - 0.06 - 0.055 * k,
                L["linen"],
                None,
            ),
        )
        F.soften(f, 0.02, 1)


def curtain(name, x0, x1, y, z0, z1, mat, coll, amp=0.045, period=0.11):
    import bmesh

    n = int((x1 - x0) / 0.008)
    m = 40
    bm = bmesh.new()
    rows = []
    for j in range(m + 1):
        z = z0 + (z1 - z0) * j / m
        row = []
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            # Pleats deepen slightly toward the hem, as gathered fabric does
            a = amp * (1.0 + 0.25 * (1 - j / m))
            row.append(bm.verts.new((x, y + a * math.sin(2 * math.pi * (x - x0) / period), z)))
        rows.append(row)
    for j in range(m):
        for i in range(n):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    obj = F.mesh_obj(name, bm, mat, None, smooth=True)
    _in(coll, obj)
    obj.modifiers.new("Solidify", "SOLIDIFY").thickness = 0.0015
    return obj


def outlet(key):
    """(x, y) in metres of a light outlet from the installation plan."""
    o = DATA["fixtures_reference"]["light_outlets"][key]
    return X(o["pt"][0]), Y(o["pt"][1])


def lights(L):
    """Ceiling fixtures from data/lighting.json, hung on the developer's light outlets."""
    c = S["lights"]
    for fx in LIGHTING["fixtures"]:
        kind, name = fx["type"], fx["id"]
        if kind == "led_strip":
            (ax, _), (_, by) = outlet(fx["outlets"][0]), outlet(fx["outlets"][1])
            led_strip(
                name,
                [(ax, fx["start_y"]), (ax, by), (fx["end_x"], by)],
                fx["width"],
                fx["w_per_m"],
                L,
                c,
            )
        elif kind == "globe_pendants":
            for i, (x, y) in enumerate(fx["at"]):
                globe_pendant(f"{name}_{i}", x, y, fx["bottom_z"], fx["w"], c)
        elif kind == "lantern":
            x, y = outlet(fx["outlet"])
            lantern(name, x, y, fx["centre_z"], fx["radius"], L, c, power=fx["w"])
        elif kind == "flush_disc":
            x, y = outlet(fx["outlet"])
            r = fx["radius"]
            _in(
                c,
                F.cyl(
                    name + "_body",
                    x,
                    y,
                    CEIL - 0.06,
                    CEIL,
                    r,
                    L["plastic_white"],
                    None,
                    segs=64,
                    bev=0.01,
                ),
            )
            _in(
                c,
                F.cyl(
                    name + "_diffuser",
                    x,
                    y,
                    CEIL - 0.062,
                    CEIL - 0.06,
                    r - 0.012,
                    L["bulb"],
                    None,
                    segs=64,
                ),
            )
            lo = _in(
                c,
                F.add_area_light(
                    name + "_light",
                    (x, y, CEIL - 0.065),
                    (2 * r - 0.03, 2 * r - 0.03),
                    fx["w"],
                    None,
                ),
            )
            lo.data.shape = "DISK"
        else:
            raise ValueError(f"{name}: unknown fixture type {kind}")


def led_strip(name, path, width, w_per_m, L, coll):
    """Recessed aluminium LED profile along a polyline of (x, y) points on the ceiling, each straight run
    with a rectangular area light under its opal diffuser."""
    for k, ((x0, y0), (x1, y1)) in enumerate(itertools.pairwise(path)):
        # Extend each run by half the width at both ends so the corners close up square
        h = width / 2
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        xa, xb, ya, yb = xa - h, xb + h, ya - h, yb + h
        _in(
            coll,
            F.box(
                f"{name}_{k}_profile",
                xa - 0.006,
                xb + 0.006,
                ya - 0.006,
                yb + 0.006,
                CEIL - 0.002,
                CEIL,
                L["steel"],
                None,
            ),
        )
        _in(
            coll,
            F.box(
                f"{name}_{k}_diffuser", xa, xb, ya, yb, CEIL - 0.003, CEIL - 0.002, L["led"], None
            ),
        )
        length = max(xb - xa, yb - ya)
        size = (xb - xa, yb - ya)
        _in(
            coll,
            F.add_area_light(
                f"{name}_{k}_light",
                ((xa + xb) / 2, (ya + yb) / 2, CEIL - 0.006),
                size,
                w_per_m * length,
                None,
            ),
        )


def globe_pendant(name, x, y, bottom_z, power, coll):
    """Poly Haven opal globe; its cord is lengthened so the globe hangs at bottom_z from the real ceiling."""
    root = ph_instance("modern_ceiling_lamp_01", name, coll)
    h = root["asset_size"][2]
    extra = CEIL - bottom_z - h
    mesh = next(o for o in root.children_recursive if o.type == "MESH")
    me = mesh.data
    if abs(me.get("cord_extra", 0.0) - extra) > 1e-4:
        # The mesh is shared by every copy: stretch it once. Everything above the globe's cap (the cord's
        # top and the ceiling canopy) moves up; the cord between stretches.
        mb = mesh.matrix_basis
        inv = mb.inverted().to_3x3()
        zs = [(mb @ v.co).z for v in me.vertices]
        z_lo, z_hi = min(zs), max(zs)
        cut = z_lo + 0.62 * (z_hi - z_lo)
        shift = inv @ Vector((0, 0, extra - me.get("cord_extra", 0.0)))
        for v, z in zip(me.vertices, zs, strict=True):
            if z > cut:
                v.co += shift
        me["cord_extra"] = extra
    root.location = (x, y, bottom_z)
    _in(
        coll,
        F.add_point_light(name + "_bulb", (x, y, bottom_z + 0.20), None, power=power, radius=0.05),
    )


def lantern(name, x, y, zc, r, L, coll, power=25):
    import bmesh

    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r)
    bmesh.ops.delete(
        bm, geom=[v for v in bm.verts if v.co.z > r * 0.93 or v.co.z < -r * 0.93], context="VERTS"
    )
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, zc))
    shade = _in(coll, F.mesh_obj(name + "_shade", bm, L["paper"], None, smooth=True))
    shade.modifiers.new("Solidify", "SOLIDIFY").thickness = 0.0015
    for k in range(1, 12):
        z = -r + 2 * r * k / 12
        rr = math.sqrt(max(r * r - z * z, 0)) + 0.001
        _in(
            coll,
            F.tube_path(
                f"{name}_rib{k}",
                F.arc_points(x, y, zc + z, rr, 0, 2 * math.pi, 48),
                0.0012,
                L["paper"],
                None,
            ),
        )
    _in(
        coll,
        F.tube_path(
            name + "_cord", [(x, y, zc + r * 0.93), (x, y, CEIL)], 0.002, L["plastic_white"], None
        ),
    )
    _in(coll, F.cyl(name + "_canopy", x, y, CEIL - 0.02, CEIL, 0.05, L["plastic_white"], None))
    lamp = F.add_point_light(name + "_bulb", (x, y, zc), None, power=power, radius=0.04)
    _in(coll, lamp)


def world_and_sun():
    """HDRI for the sky and the view outside; its sun disc is clamped out and replaced by a Sun lamp aimed
    through the windows. Camera and transmission rays still see the full HDRI, so the view stays bright."""
    scene = bpy.context.scene
    img = bpy.data.images.load(str(PH / "hdris" / HDRI), check_existing=True)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    lum = 0.2126 * px[..., 0] + 0.7152 * px[..., 1] + 0.0722 * px[..., 2]
    iy, ix = np.unravel_index(np.argmax(lum), lum.shape)
    u, v = (ix + 0.5) / w, (iy + 0.5) / h
    phi, theta = (u - 0.5) * 2 * math.pi, (v - 0.5) * math.pi
    d_tex = Vector(
        (-math.cos(phi) * math.cos(theta), math.sin(phi) * math.cos(theta), math.sin(theta))
    )
    lat = (np.arange(h) + 0.5) / h * math.pi - math.pi / 2
    d_omega = (2 * math.pi / w) * (math.pi / h) * np.cos(lat)[:, None]
    sun_irradiance = float(np.sum(np.clip(lum - HDRI_CLAMP, 0, None) * d_omega))
    sun_az, sun_el = sun_in_plan()
    print(f"Sun for {SITE['date_time']}: {sun_az:.1f} deg from +X, {sun_el:.1f} deg high")
    rot = math.atan2(d_tex.y, d_tex.x) - math.radians(sun_az)
    print(
        f"HDRI sun at elevation {math.degrees(theta):.1f} deg; clamped-out irradiance {sun_irradiance:.1f} W/m2"
    )

    world = bpy.data.worlds.new("World_HDRI")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    tc = nodes.new("ShaderNodeTexCoord")
    mp = nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = rot
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = img
    links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    links.new(mp.outputs["Vector"], env.inputs["Vector"])
    clamp = nodes.new("ShaderNodeVectorMath")
    clamp.operation = "MINIMUM"
    clamp.inputs[1].default_value = (HDRI_CLAMP,) * 3
    links.new(env.outputs["Color"], clamp.inputs[0])
    strength = nodes.new("ShaderNodeValue")
    strength.name = "World_Strength"
    strength.outputs[0].default_value = 1.0
    bg_light = nodes.new("ShaderNodeBackground")
    bg_view = nodes.new("ShaderNodeBackground")
    links.new(clamp.outputs["Vector"], bg_light.inputs["Color"])
    links.new(env.outputs["Color"], bg_view.inputs["Color"])
    links.new(strength.outputs[0], bg_light.inputs["Strength"])
    links.new(strength.outputs[0], bg_view.inputs["Strength"])
    lp = nodes.new("ShaderNodeLightPath")
    mx = nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    links.new(lp.outputs["Is Camera Ray"], mx.inputs[0])
    links.new(lp.outputs["Is Transmission Ray"], mx.inputs[1])
    mix = nodes.new("ShaderNodeMixShader")
    links.new(mx.outputs[0], mix.inputs["Fac"])
    links.new(bg_light.outputs[0], mix.inputs[1])
    links.new(bg_view.outputs[0], mix.inputs[2])
    out = nodes.new("ShaderNodeOutputWorld")
    links.new(mix.outputs[0], out.inputs["Surface"])

    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = max(3.0, min(sun_irradiance, 12.0))
    sun.angle = math.radians(1.0)
    sun.color = (1.0, 0.95, 0.88)
    so = bpy.data.objects.new("Sun", sun)
    el, az = math.radians(sun_el), math.radians(sun_az)
    to_sun = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    so.rotation_euler = to_sun.to_track_quat("Z", "Y").to_euler()
    S["lights"].objects.link(so)


def exterior(L):
    """The balcony dressed (deck, railing) and what is seen from the 2nd floor: this building's facade below
    and beside the flat, the courtyard 6 m down with lawn, path, trees and shrubs, and the block opposite."""
    c = shell.collection("Site")
    grade = -shell.H["floor_above_grade"]
    b = DATA["balcony"]
    bz = shell.H["balcony_floor_offset"]
    sx0, sx1, sy0, sy1 = shell.rect_m(b["slab_pt"])
    rx0, rx1, ry0, ry1 = shell.rect_m(b["railing_pt"])
    # The shell's structural slab spans the balcony too and pokes up through it: keep it to the heated area
    xs = [v for w in DATA["walls"] for v in shell.rect_m(w["rect_pt"])[:2]]
    ys = [v for w in DATA["walls"] for v in shell.rect_m(w["rect_pt"])[2:]]
    bpy.data.objects.remove(bpy.data.objects["Structural_Slab"])
    footprint = [(min(xs), max(xs), min(ys), sy0), (sx1, max(xs), sy0, max(ys))]
    for i, (x0, x1, y0, y1) in enumerate(footprint):
        _in(
            S["arch"],
            F.box(f"Structural_Slab_{i}", x0, x1, y0, y1, -0.22, -0.02, L["balcony"], None),
        )
        _in(c, F.box(f"Facade_below_{i}", x0, x1, y0, y1, grade, -0.22, L["facade"], None))
    # Balcony: oak deck boards, frameless glass in a graphite base channel with a graphite handrail
    _in(
        c,
        F.box(
            "Balcony_Deck", sx0, sx1, sy0, sy1, bz, bz + 0.02, L["balcony_deck"], None, bev=0.002
        ),
    )
    bpy.data.objects.remove(bpy.data.objects["Balcony_Railing"])
    rh = shell.H["balcony_railing"]
    ym = (ry0 + ry1) / 2
    _in(
        c,
        F.box(
            "Railing_channel",
            rx0,
            rx1,
            ym - 0.03,
            ym + 0.03,
            bz,
            bz + 0.10,
            L["graphite"],
            None,
            bev=0.003,
        ),
    )
    _in(
        c,
        F.box(
            "Railing_glass",
            rx0 + 0.01,
            rx1 - 0.01,
            ym - 0.008,
            ym + 0.008,
            bz + 0.10,
            bz + rh - 0.06,
            L["glass_railing"],
            None,
        ),
    )
    _in(
        c,
        F.box(
            "Railing_handrail",
            rx0,
            rx1,
            ym - 0.03,
            ym + 0.03,
            bz + rh - 0.04,
            bz + rh,
            L["graphite"],
            None,
            bev=0.004,
        ),
    )
    for i, x in enumerate((rx0 + 0.03, rx1 - 0.03)):
        _in(
            c,
            F.box(
                f"Railing_post_{i}",
                x - 0.02,
                x + 0.02,
                ym - 0.02,
                ym + 0.02,
                bz + 0.10,
                bz + rh - 0.04,
                L["graphite"],
                None,
            ),
        )
    # Courtyard
    _in(c, F.box("Ground", -200, 200, -200, 200, grade - 0.1, grade, L["grass"], None))
    for i, p in enumerate(SITE["paths"]):
        x0, x1, y0, y1 = p["rect"]
        _in(c, F.box(f"Path_{i}", x0, x1, y0, y1, grade, grade + 0.02, L["paving"], None))
    for kind in ("trees", "shrubs"):
        for i, t in enumerate(SITE[kind]):
            root = ph_instance(t["asset"], f"{kind}_{i}_{t['asset']}", c)
            k = t["height"] / root["asset_size"][2]
            root.scale = (k, k, k)
            root.location = (t["at"][0], t["at"][1], grade)
            root.rotation_euler.z = math.radians(t.get("rot", 0))
    for i, bd in enumerate(SITE["buildings"]):
        x0, x1, y0, y1 = bd["rect"]
        z0, z1 = bd.get("z_bottom", grade), bd["z_top"]
        _in(
            c, F.box(f"Building_{i}", x0, x1, y0, y1, z0, z1, L[bd.get("material", "facade")], None)
        )
        if bd.get("windows"):
            facade_bays(f"Building_{i}", x0, x1, y0, z0, z1, L, c)


def facade_bays(name, x0, x1, y, z0, z1, L, c):
    """Dress a facade facing -Y: a dark plinth, a parapet, and per storey 3 m bays of recessed framed windows;
    every third bay is a balcony door with a slab and a glass railing."""
    _in(
        c,
        F.box(
            name + "_plinth",
            x0 - 0.05,
            x1 + 0.05,
            y - 0.05,
            y + 0.5,
            z0,
            z0 + 0.9,
            L["front_greige"],
            None,
        ),
    )
    _in(
        c,
        F.box(
            name + "_parapet",
            x0 - 0.05,
            x1 + 0.05,
            y - 0.05,
            y + 0.5,
            z1,
            z1 + 0.6,
            L["graphite"],
            None,
        ),
    )
    storeys = int((z1 - z0 - 0.9) // 2.95)
    bays = int((x1 - x0 - 1.0) // 3.0)
    for f in range(storeys):
        zf = z0 + 0.9 + 2.95 * f
        for j in range(bays):
            xb = x0 + 0.5 + 3.0 * j
            door = (j + f) % 3 == 0 and f > 0
            wx0, wx1 = xb + 0.75, xb + 2.25
            wz0, wz1 = (zf, zf + 2.2) if door else (zf + 0.85, zf + 2.2)
            n = f"{name}_{f}_{j}"
            # Reveal (a dark recess), the frame and the glass
            _in(
                c,
                F.box(
                    n + "_reveal",
                    wx0,
                    wx1,
                    y - 0.001,
                    y + 0.001,
                    wz0,
                    wz1,
                    L["plastic_black"],
                    None,
                ),
            )
            _in(
                c,
                F.box(
                    n + "_frame",
                    wx0 + 0.0,
                    wx1 - 0.0,
                    y - 0.04,
                    y - 0.001,
                    wz0,
                    wz0 + 0.05,
                    L["graphite"],
                    None,
                ),
            )
            _in(
                c,
                F.box(
                    n + "_frame_t",
                    wx0,
                    wx1,
                    y - 0.04,
                    y - 0.001,
                    wz1 - 0.05,
                    wz1,
                    L["graphite"],
                    None,
                ),
            )
            _in(
                c,
                F.box(
                    n + "_mull",
                    (wx0 + wx1) / 2 - 0.025,
                    (wx0 + wx1) / 2 + 0.025,
                    y - 0.04,
                    y - 0.001,
                    wz0 + 0.05,
                    wz1 - 0.05,
                    L["graphite"],
                    None,
                ),
            )
            _in(
                c,
                F.box(
                    n + "_glass",
                    wx0,
                    wx1,
                    y - 0.03,
                    y - 0.02,
                    wz0 + 0.05,
                    wz1 - 0.05,
                    L["black_glass"],
                    None,
                ),
            )
            if door:
                _in(
                    c,
                    F.box(
                        n + "_slab",
                        xb + 0.2,
                        xb + 2.8,
                        y - 1.3,
                        y - 0.001,
                        zf - 0.2,
                        zf,
                        L["facade"],
                        None,
                    ),
                )
                _in(
                    c,
                    F.box(
                        n + "_rail",
                        xb + 0.2,
                        xb + 2.8,
                        y - 1.3,
                        y - 1.28,
                        zf,
                        zf + 1.1,
                        L["glass_railing"],
                        None,
                    ),
                )


def cameras():
    c = S["cams"]
    for name, cfg in CAMS.items():
        cam = bpy.data.cameras.new("Cam_" + name)
        cam.lens = cfg["lens"]
        cam.sensor_width = 36
        cam.shift_y = cfg.get("shift_y", 0.0)
        cam.clip_start = 0.05
        obj = bpy.data.objects.new("Cam_" + name, cam)
        obj.location = cfg["loc"]
        dx, dy = cfg["target"][0] - cfg["loc"][0], cfg["target"][1] - cfg["loc"][1]
        obj.rotation_euler = (
            math.pi / 2,
            0,
            math.atan2(-dx, dy),
        )  # level camera, yaw toward the target
        c.objects.link(obj)
    bpy.context.scene.camera = bpy.data.objects["Cam_walk"]


def render_settings():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.samples = 256
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 12, 6, 4
    cy.transmission_bounces, cy.transparent_max_bounces = 12, 16
    cy.sample_clamp_indirect = 10.0
    cy.blur_glossy = 0.5
    cy.caustics_reflective = cy.caustics_refractive = False
    scene.render.resolution_x, scene.render.resolution_y = 1800, 1200
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = (
        2.0  # interiors are exposed like a real camera would: ~+1.5 EV over the sky
    )
    scene.render.film_transparent = False
    # Viewport: material preview is the comfortable mode for walking around
    scene.display.shading.light = "STUDIO"


def main():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / "blender" / "apartment_shell.blend"))
    L = materials.library()
    F.CEIL = CEIL
    F.M.clear()
    F.M.update(L)
    S.update(
        arch=bpy.data.collections["Architecture"],
        walls=bpy.data.collections["Walls"],
        floors=bpy.data.collections["Floors"],
        ceilings=bpy.data.collections["Ceilings"],
        openings=bpy.data.collections["Openings"],
    )
    S["finishes"] = shell.collection("Finishes", S["arch"])
    S["doors"] = shell.collection("Doors", S["arch"])
    S["furniture"] = shell.collection("Furniture")
    S["decor"] = shell.collection("Decor")
    S["textiles"] = shell.collection("Textiles")
    S["lights"] = shell.collection("Lighting")
    S["cams"] = bpy.data.collections["Cameras_Lights"]
    old_sun = bpy.data.objects.get("Sun")
    if old_sun:
        bpy.data.objects.remove(old_sun)
    for name in ("Cam_Overview_SW", "Cam_Overview_NW"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name])
    bpy.data.collections["Ceilings"].hide_render = False

    restyle(L)
    finishes(L)
    doors(L)
    furniture()
    decor()
    curtains(L)
    lights(L)
    exterior(L)
    world_and_sun()
    cameras()
    render_settings()
    modes.set_mode("day")
    # Cached Poly Haven originals sit in collections outside the scene; they are dropped on save
    out = ROOT / "blender" / "apartment.blend"
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("Saved", out)


if __name__ == "__main__":
    main()
