"""Procedural furniture generators, keyed by the 'proc:<type>' source in data/furniture.json.

Local frame for every generator: width w along +X in [0, w], depth d along +Y in [0, d], front face at y = 0
(facing -Y), back at y = d (against the wall), height along +Z from the floor. place() maps the frame onto the
item's world footprint and facing. Dimensions are metres.
"""

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix

IMAGES = Path(__file__).resolve().parent.parent / "assets" / "images"

M = {}  # material library, set by build_interior.py
CEIL = 2.95  # ceiling height; build_interior.py sets it from data/floorplan.json


# ---------------------------------------------------------------- primitives


def _link(obj, parent):
    coll = parent.users_collection[0] if parent else bpy.context.scene.collection
    coll.objects.link(obj)
    if parent:
        obj.parent = parent
    return obj


def mesh_obj(name, bm, mat, parent, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    obj = bpy.data.objects.new(name, me)
    if mat:
        me.materials.append(mat)
    return _link(obj, parent)


def bevel(obj, width=0.003, segments=2, angle=None):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE" if angle else "NONE"
    if angle:
        mod.angle_limit = math.radians(angle)
    mod.harden_normals = True
    obj.data.shade_smooth()
    return obj


def soften(obj, radius, levels=2):
    """Upholstery look: big bevel then subdivision, smooth shaded."""
    b = obj.modifiers.new("Bevel", "BEVEL")
    b.width = radius
    b.segments = 3
    b.limit_method = "NONE"
    s = obj.modifiers.new("Subsurf", "SUBSURF")
    s.levels = levels
    s.render_levels = levels
    obj.data.shade_smooth()
    return obj


def box_c(name, sx, sy, sz, center, mat, parent):
    """Box built around its own origin and placed at center, so rotations pivot on the box itself."""
    obj = box(name, -sx / 2, sx / 2, -sy / 2, sy / 2, -sz / 2, sz / 2, mat, parent)
    obj.location = center
    return obj


def box(name, x0, x1, y0, y1, z0, z1, mat, parent, bev=0.0, seg=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    obj = mesh_obj(name, bm, mat, parent)
    if bev:
        bevel(obj, bev, seg)
    return obj


def cyl(name, x, y, z0, z1, r, mat, parent, r_top=None, segs=32, bev=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=segs,
        radius1=r,
        radius2=r if r_top is None else r_top,
        depth=z1 - z0,
    )
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, (z0 + z1) / 2))
    obj = mesh_obj(name, bm, mat, parent, smooth=True)
    if bev:
        bevel(obj, bev, 2, angle=60)
    return obj


def tube_path(name, points, r, mat, parent, segs=12):
    """A round tube along a polyline (towel rails, taps, chair rails). Points are local (x, y, z)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = max(2, segs // 4)
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, v in zip(sp.points, points):
        p.co = (*v, 1.0)
    obj = bpy.data.objects.new(name, cu)
    if mat:
        cu.materials.append(mat)
    return _link(obj, parent)


def arc_points(cx, cy, z, r, a0, a1, n=16):
    return [
        (cx + r * math.cos(a), cy + r * math.sin(a), z)
        for a in (a0 + (a1 - a0) * i / (n - 1) for i in range(n))
    ]


def empty(name, coll):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "PLAIN_AXES"
    e.empty_display_size = 0.2
    coll.objects.link(e)
    return e


def settle(obj, z_surface, sink=0.008):
    """Drop a soft object (pillow, cushion) so its lowest evaluated vertex rests on z_surface, pressed in
    by sink. Works in the parent's frame, so call it before the root is placed."""
    bpy.context.view_layer.update()
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    zmin = min((obj.matrix_basis @ v.co).z for v in me.vertices)
    ev.to_mesh_clear()
    obj.location.z += z_surface - sink - zmin
    return obj


def add_area_light(name, loc, size, power, parent, color=(1.0, 0.82, 0.62)):
    """Rectangular area light shining down (-Z), tagged as a lamp for the day/evening switch."""
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size
    ld.energy = power
    ld.color = color
    obj = bpy.data.objects.new(name, ld)
    obj.location = loc
    obj["role"] = "lamp"
    obj["power_on"] = power
    return _link(obj, parent)


# ---------------------------------------------------------------- placement


def frame_dims(item):
    """(width, depth) of the local frame for an item's footprint and facing."""
    x0, x1, y0, y1 = item["footprint"]
    if item["facing"] in ("+y", "-y"):
        return x1 - x0, y1 - y0
    return y1 - y0, x1 - x0


def place(root, item):
    x0, x1, y0, y1 = item["footprint"]
    f = item["facing"]
    if f == "-y":
        root.location, rz = (x0, y0, 0), 0.0
    elif f == "+y":
        root.location, rz = (x1, y1, 0), math.pi
    elif f == "+x":
        root.location, rz = (x1, y0, 0), math.pi / 2
    else:  # -x
        root.location, rz = (x0, y1, 0), -math.pi / 2
    root.rotation_euler = (0, 0, rz)


def world_to_local_x(item, world):
    """Convert a world coordinate along the item's width axis into local x."""
    x0, x1, y0, y1 = item["footprint"]
    return {"-y": world - x0, "+y": x1 - world, "+x": world - y0, "-x": y1 - world}[item["facing"]]


# ---------------------------------------------------------------- kitchen

PLINTH = 0.10
TOP_T = 0.03
GAP = 0.003
FRONT_T = 0.019


def _pull(name, cx, z, parent, length=0.16):
    """Slim matte-black bar pull, horizontal, on a front at y = 0."""
    tube_path(
        name,
        [(cx - length / 2, -0.028, z), (cx + length / 2, -0.028, z)],
        0.006,
        M["black_metal"],
        parent,
    )
    for sx in (cx - length / 2 + 0.01, cx + length / 2 - 0.01):
        tube_path(name + "_post", [(sx, -0.028, z), (sx, 0.0, z)], 0.004, M["black_metal"], parent)


def _drawer_stack(name, x0, x1, z0, z1, parent, n=3, mat=None):
    mat = mat or M["oak"]
    heights = [0.25, 0.375, 0.375][:n] if n == 3 else [1 / n] * n
    tot = z1 - z0
    z = z0
    for i, f in enumerate(heights):
        h = tot * f
        box(
            f"{name}_drawer{i}",
            x0 + GAP,
            x1 - GAP,
            -FRONT_T,
            0,
            z + GAP,
            z + h - GAP,
            mat,
            parent,
            bev=0.0015,
        )
        _pull(f"{name}_pull{i}", (x0 + x1) / 2, z + h - 0.045, parent)
        z += h


def _door_pair(name, x0, x1, z0, z1, parent, mat=None, pulls="top"):
    mat = mat or M["oak"]
    xm = (x0 + x1) / 2
    for i, (a, b) in enumerate(((x0, xm), (xm, x1))):
        box(
            f"{name}_door{i}",
            a + GAP,
            b - GAP,
            -FRONT_T,
            0,
            z0 + GAP,
            z1 - GAP,
            mat,
            parent,
            bev=0.0015,
        )
        px = b - 0.06 if i == 0 else a + 0.06
        if pulls == "top":
            _pull(f"{name}_pull{i}", px, z1 - 0.05, parent, 0.12)


def sink(name, cx, depth, parent):
    """Undermount steel sink + black gooseneck tap; returns the worktop cutter."""
    w, d, h = 0.50, 0.40, 0.19
    cy = depth / 2 - 0.02
    zt = 0.90 - TOP_T
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = cx - w / 2 - 0.01 if v.co.x < 0 else cx + w / 2 + 0.01
        v.co.y = cy - d / 2 - 0.01 if v.co.y < 0 else cy + d / 2 + 0.01
        v.co.z = zt - h if v.co.z < 0 else zt
    top = next(f for f in bm.faces if f.normal.z > 0.5)
    r = bmesh.ops.inset_region(bm, faces=[top], thickness=0.01, depth=0)
    bmesh.ops.translate(bm, verts=top.verts, vec=(0, 0, -(h - 0.01)))
    basin = mesh_obj(name + "_basin", bm, M["steel"], parent)
    bevel(basin, 0.004, 3, angle=40)
    cyl(name + "_drain", cx, cy, zt - h + 0.008, zt - h + 0.012, 0.045, M["steel"], parent)
    # Tap behind the sink
    tx, ty = cx, cy + d / 2 + 0.06
    cyl(name + "_tap_base", tx, ty, 0.90, 0.915, 0.028, M["black_metal"], parent)
    r = 0.10  # gooseneck: straight up, a half-circle toward the sink, then a short drop
    arc = [
        (tx, ty - r + r * math.cos(a), 1.12 + r * math.sin(a))
        for a in (math.radians(t) for t in range(0, 181, 15))
    ]
    tube_path(
        name + "_tap",
        [(tx, ty, 0.9), *arc, (tx, ty - 2 * r, 1.06)],
        0.011,
        M["black_metal"],
        parent,
    )
    tube_path(
        name + "_lever",
        [(tx + 0.02, ty, 1.0), (tx + 0.09, ty + 0.01, 1.03)],
        0.005,
        M["black_metal"],
        parent,
    )
    cutter = box(
        name + "_cut", cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, 0.80, 1.0, None, parent
    )
    return cutter


def hob(name, cx, depth, parent):
    w, d = 0.59, 0.52
    cy = depth / 2 - 0.01
    box(
        name,
        cx - w / 2,
        cx + w / 2,
        cy - d / 2,
        cy + d / 2,
        0.90,
        0.905,
        M["black_glass"],
        parent,
        bev=0.001,
    )
    # Faint zone rings printed on the glass
    for i, (ox, oy, r) in enumerate(
        ((-0.14, -0.11, 0.09), (0.14, -0.11, 0.08), (-0.14, 0.12, 0.08), (0.14, 0.12, 0.10))
    ):
        ring = tube_path(
            f"{name}_zone{i}",
            arc_points(cx + ox, cy + oy, 0.9052, r, 0, 2 * math.pi, 48),
            0.0012,
            M["plastic_white"],
            parent,
        )
        ring.data.bevel_resolution = 1


def _cut(target, cutter):
    mod = target.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter)


def kitchen_run(item, root):
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    box(n + "_plinth", 0, w, 0.05, d - 0.02, 0, PLINTH, M["plastic_black"], root)
    box(n + "_carcass", 0, w, 0.0, d - 0.015, PLINTH, 0.90 - TOP_T, M["front_white"], root)
    top = box(n + "_worktop", 0, w, -0.025, d - 0.015, 0.90 - TOP_T, 0.90, M["worktop"], root)
    box(n + "_splash", 0, w, d - 0.015, d, 0.90, 1.50, M["worktop"], root, bev=0.001)

    specials = []
    if "sink_at" in p:
        sx = world_to_local_x(item, p["sink_at"])
        specials.append(("sink", sx - 0.30, sx + 0.30))
        _cut(top, sink(n + "_sink", sx, d, root))
    if "dishwasher" in p:
        a, b = sorted(world_to_local_x(item, v) for v in p["dishwasher"])
        specials.append(("dw", a, b))
    if "small_door" in p:
        a, b = sorted(world_to_local_x(item, v) for v in p["small_door"])
        specials.append(("door1", a, b))
    if "hob_at" in p:
        hx = world_to_local_x(item, p["hob_at"])
        hob(n + "_hob", hx, d, root)
        specials.append(("hob", hx - 0.30, hx + 0.30))
    specials.sort(key=lambda s: s[1])
    bevel(top, 0.002)

    # Fill the run: specials at their spot, drawer stacks in the gaps
    cursor, i = 0.0, 0
    zf0, zf1 = PLINTH, 0.90 - TOP_T
    for kind, a, b in [*specials, ("end", w, w)]:
        a, b = max(a, cursor), min(b, w)
        while a - cursor > 0.15:
            seg_end = min(a, cursor + 0.60) if a - cursor > 0.75 else a
            _drawer_stack(f"{n}_mod{i}", cursor, seg_end, zf0, zf1, root)
            cursor, i = seg_end, i + 1
        if a - cursor > 0.002:  # narrow leftover: a filler strip, as a kitchen fitter would do
            box(
                f"{n}_filler{i}",
                cursor + GAP,
                a - GAP,
                -FRONT_T,
                0,
                zf0 + GAP,
                zf1 - GAP,
                M["oak"],
                root,
            )
            cursor = a
        if kind == "sink":
            _door_pair(f"{n}_sinkdoors", a, b, zf0, zf1, root)
        elif kind == "dw":
            box(
                f"{n}_dwfront",
                a + GAP,
                b - GAP,
                -FRONT_T,
                0,
                zf0 + GAP,
                zf1 - GAP,
                M["oak"],
                root,
                bev=0.0015,
            )
            _pull(f"{n}_dwpull", (a + b) / 2, zf1 - 0.05, root)
        elif kind == "door1":
            # Narrow single-door cabinet closing the run next to the entrance
            box(
                f"{n}_smalldoor",
                a + GAP,
                b - GAP,
                -FRONT_T,
                0,
                zf0 + GAP,
                zf1 - GAP,
                M["oak"],
                root,
                bev=0.0015,
            )
            _pull(f"{n}_smalldoor_pull", (a + b) / 2, zf1 - 0.05, root, 0.10)
        elif kind == "hob" and p.get("oven_under_hob"):
            # Built-in oven under the hob, with a shallow drawer below it
            box(
                f"{n}_ovendrawer",
                a + GAP,
                b - GAP,
                -FRONT_T,
                0,
                zf0 + GAP,
                0.25 - GAP,
                M["oak"],
                root,
                bev=0.0015,
            )
            _pull(f"{n}_ovendrawer_pull", (a + b) / 2, 0.20, root)
            box(
                f"{n}_oven",
                a + GAP,
                b - GAP,
                -0.022,
                0,
                0.25 + GAP,
                zf1 - GAP,
                M["black_glass"],
                root,
                bev=0.002,
            )
            box(
                f"{n}_oven_panel",
                a + 0.02,
                b - 0.02,
                -0.024,
                -0.021,
                zf1 - 0.08,
                zf1 - 0.02,
                M["steel"],
                root,
            )
            tube_path(
                f"{n}_oven_handle",
                [(a + 0.08, -0.045, zf1 - 0.11), (b - 0.08, -0.045, zf1 - 0.11)],
                0.008,
                M["steel"],
                root,
            )
        elif kind == "hob":
            _drawer_stack(f"{n}_hobdrawers", a, b, zf0, zf1, root, n=2)
        if kind != "end":
            cursor = b
    if w - cursor > 0.01:
        _drawer_stack(f"{n}_modlast", cursor, w, zf0, zf1, root)


def tall_unit(item, root):
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    top = item["z"][1]
    W = M["front_white"]
    box(n + "_plinth", 0, w, 0.05, d - 0.02, 0, PLINTH, M["plastic_black"], root)
    box(n + "_carcass", 0, w, 0.0, d, PLINTH, top, W, root)
    if CEIL - top > 0.005:
        box(n + "_filler", 0, w, 0.02, d, top, CEIL, W, root)  # scribe to ceiling
    if p.get("fridge"):
        # Integrated fridge-freezer behind two doors, a top-box cupboard above it
        fz = min(top, 2.10)
        box(
            n + "_door_low",
            GAP,
            w - GAP,
            -FRONT_T,
            0,
            PLINTH + GAP,
            1.20 - GAP,
            W,
            root,
            bev=0.0015,
        )
        box(n + "_door_up", GAP, w - GAP, -FRONT_T, 0, 1.20 + GAP, fz - GAP, W, root, bev=0.0015)
        if top - fz > 0.15:
            box(
                n + "_door_top", GAP, w - GAP, -FRONT_T, 0, fz + GAP, top - GAP, W, root, bev=0.0015
            )
        handle = [(0.05, -0.03, 0.75), (0.05, -0.03, 1.15)]
        tube_path(n + "_handle", handle, 0.007, M["black_metal"], root)
        handle2 = [(0.05, -0.03, 1.25), (0.05, -0.03, 1.65)]
        tube_path(n + "_handle2", handle2, 0.007, M["black_metal"], root)
    if p.get("oven"):
        _drawer_stack(n + "_low", 0, w, PLINTH, 0.80, root, n=2, mat=W)
        box(
            n + "_oven",
            GAP,
            w - GAP,
            -0.022,
            0,
            0.80 + GAP,
            1.40 - GAP,
            M["black_glass"],
            root,
            bev=0.002,
        )
        box(
            n + "_oven_panel",
            GAP + 0.02,
            w - GAP - 0.02,
            -0.024,
            -0.021,
            1.32,
            1.38,
            M["steel"],
            root,
        )
        bar = [(0.08, -0.045, 1.29), (w - 0.08, -0.045, 1.29)]
        tube_path(n + "_oven_handle", bar, 0.008, M["steel"], root)
        box(n + "_top_door", GAP, w - GAP, -FRONT_T, 0, 1.40 + GAP, top - GAP, W, root, bev=0.0015)
        _pull(n + "_top_pull", w / 2, 1.45, root)


def upper_run(item, root):
    w, d = frame_dims(item)
    n = item["id"]
    z0, z1 = item["z"]
    p = item.get("params", {})
    box(n + "_carcass", 0, w, 0.0, d, z0, z1, M["front_white"], root)
    if CEIL - z1 > 0.005:
        box(n + "_filler", 0, w, 0.02, d, z1, CEIL, M["front_white"], root)
    k = max(1, round(w / 0.45))
    # Runs that go up to a high ceiling get a second row of top-box doors over the everyday ones
    rows = [(z0, z0 + 0.72), (z0 + 0.72, z1)] if z1 - z0 > 1.0 else [(z0, z1)]
    for r, (za, zb) in enumerate(rows):
        for i in range(k):
            a, b = w * i / k, w * (i + 1) / k
            box(
                f"{n}_door{r}_{i}",
                a + GAP,
                b - GAP,
                -FRONT_T,
                0,
                za + GAP,
                zb - GAP,
                M["front_white"],
                root,
                bev=0.0015,
            )
    # Under-cabinet LED strip and the integrated hood underside
    box(n + "_led", 0.02, w - 0.02, 0.04, 0.06, z0 - 0.004, z0 - 0.001, M["led"], root)
    if "hood_at" in p:
        hx = world_to_local_x(item, p["hood_at"])
        box(
            n + "_hood",
            hx - 0.28,
            hx + 0.28,
            0.02,
            d - 0.03,
            z0 - 0.008,
            z0,
            M["steel"],
            root,
            bev=0.001,
        )


def open_shelves(item, root):
    w, d = frame_dims(item)
    z0, z1 = item["z"]
    count = item.get("params", {}).get("count", 2)
    for i in range(count):
        z = z0 + (z1 - z0) * i / max(1, count - 1) - 0.04 * (i == count - 1)
        box(f"{item['id']}_{i}", 0, w, 0.0, d, z, z + 0.04, M["oak"], root, bev=0.002)


def peninsula(item, root):
    """Third leg of the U: base cabinets that run on into a floating counter, open beneath, carried at the
    far end by a single waterfall slab. One continuous stone top; a 30 cm overhang on the back is knee room."""
    w, d = frame_dims(item)  # facing -y: local x = world X, front (y = 0) faces into the U
    p = item.get("params", {})
    n = item["id"]
    cab_to, cab_d = p.get("cabinets_to", 1.8), p.get("cabinet_depth", 0.6)
    tt = p.get("top_thickness", 0.06)
    top_z = item["z"][1]
    box(n + "_plinth", 0.0, cab_to, 0.05, cab_d - 0.03, 0, PLINTH, M["plastic_black"], root)
    box(n + "_carcass", 0.0, cab_to, 0.0, cab_d, PLINTH, top_z - tt, M["front_white"], root)
    box(n + "_back", 0.0, cab_to, cab_d, cab_d + 0.019, 0.0, top_z - tt, M["oak"], root, bev=0.002)
    # The first 60 cm sit behind the oven column's end: a blind corner with a plain panel
    zf0, zf1 = PLINTH, top_z - tt
    corner = 0.60
    box(n + "_blind", 0.0, corner, -FRONT_T, 0, zf0 + GAP, zf1 - GAP, M["oak"], root)
    if "dishwasher" in p:
        dw0, dw1 = p["dishwasher"]
        if dw0 - corner > 0.15:
            _drawer_stack(n + "_drawers_a", corner, dw0, zf0, zf1, root)
        box(
            n + "_dwfront",
            dw0 + GAP,
            dw1 - GAP,
            -FRONT_T,
            0,
            zf0 + GAP,
            zf1 - GAP,
            M["oak"],
            root,
            bev=0.0015,
        )
        _pull(n + "_dwpull", (dw0 + dw1) / 2, zf1 - 0.05, root)
        rest = dw1
    else:  # no appliance: ordinary drawer stacks, at most 60 cm wide
        k = max(1, round((cab_to - corner) / 0.60))
        for i in range(k):
            x0 = corner + (cab_to - corner) * i / k
            x1 = corner + (cab_to - corner) * (i + 1) / k
            _drawer_stack(f"{n}_drawers{i}", x0, x1, zf0, zf1, root)
        rest = cab_to
    if cab_to - rest > 0.15:
        _drawer_stack(n + "_drawers_b", rest, cab_to, zf0, zf1, root)
    # Counter over the cabinets; past them the same stone steps down to table height and runs to the
    # waterfall end, open beneath. A stone end panel closes the cabinets where the step is.
    # The dining part (table, its end panel and the waterfall leg) can be solid oak instead of stone.
    table_z = p.get("table_height", top_z)
    tm = M[p.get("table_material", "worktop")]
    box(
        n + "_top",
        0.0,
        cab_to + 0.02,
        -0.025,
        d,
        top_z - tt,
        top_z,
        M["worktop"],
        root,
        bev=0.003,
        seg=3,
    )
    if table_z < top_z - 0.01:
        box(n + "_endpanel", cab_to, cab_to + 0.02, -0.025, d, 0.0, top_z - tt, tm, root, bev=0.002)
        box(
            n + "_table",
            cab_to + 0.02,
            w,
            -0.025,
            d,
            table_z - tt,
            table_z,
            tm,
            root,
            bev=0.003,
            seg=3,
        )
    else:
        box(
            n + "_table", cab_to + 0.02, w, -0.025, d, top_z - tt, top_z, tm, root, bev=0.003, seg=3
        )
    box(
        n + "_waterfall",
        w - tt,
        w,
        -0.025,
        d,
        0.0,
        min(table_z, top_z) - tt,
        tm,
        root,
        bev=0.003,
        seg=3,
    )


def divider_wall(item, root):
    """Short plastered partition at the peninsula's wall end, screening the sink side from the sofa."""
    w, d = frame_dims(item)
    box(item["id"], 0, w, 0, d, item["z"][0], item["z"][1], M["wall"], root, bev=0.004)


def partition(item, root):
    """Floor-to-ceiling plasterboard partition in a paint colour with white skirting on the faces listed in
    params.skirting ("front" = local -Y). params.remove lists shell objects it replaces, such as a door
    architrave it would swallow."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    box(n, 0, w, 0, d, 0.0, CEIL, M[p.get("material", "wall")], root)
    for side, (a, b) in (("front", (-0.012, 0.0)), ("back", (d, d + 0.012))):
        if side in p.get("skirting", ("front", "back")):
            box(f"{n}_skirting_{side}", 0, w, a, b, 0.0, 0.06, M["skirting"], root)
    for name in p.get("remove", []):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)


def slat_screen(item, root):
    """Openwork (Polish "ażurowa") room divider: vertical oak slats floor to ceiling, with gaps you see
    through, held by a slim floor rail and ceiling rail. Slats run along the item's width."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    mat = M[p.get("material", "oak")]
    sw, gap = p.get("slat_width", 0.04), p.get("gap", 0.03)
    rail = 0.03
    box(n + "_floor_rail", 0, w, 0, d, 0.0, rail, mat, root, bev=0.002)
    box(n + "_ceiling_rail", 0, w, 0, d, CEIL - rail, CEIL, mat, root, bev=0.002)
    k = max(1, int((w + gap) // (sw + gap)))
    x = (w - (k * sw + (k - 1) * gap)) / 2
    for i in range(k):
        box(f"{n}_slat{i}", x, x + sw, 0.0, d, rail, CEIL - rail, mat, root, bev=0.003)
        x += sw + gap
    for name in p.get("remove", []):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)


def open_unit(item, root):
    """Free-standing oak storage tower that matches the media wall: closed slat-door cabinets and open,
    see-through shelf bays (no back, so you see across the room) stacked as `levels` [z0, z1, "closed" or
    "open"], from the plinth to the top. Doors face the front; the closed bays have an oak back."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n, top = item["id"], item["z"][1]
    sh, back = 0.019, 0.012
    box(n + "_plinth", sh, w - sh, 0.05, d - back, 0.0, 0.06, M["plastic_black"], root)
    box(n + "_sideL", 0, sh, 0.0, d, 0.0, top, M["oak"], root, bev=0.001)
    box(n + "_sideR", w - sh, w, 0.0, d, 0.0, top, M["oak"], root, bev=0.001)
    for j, (z0, z1, kind) in enumerate(p["levels"]):
        box(f"{n}_board{j}", sh, w - sh, 0.0, d - back, z0, z0 + 0.022, M["oak"], root, bev=0.001)
        if kind == "closed":
            box(f"{n}_back{j}", sh, w - sh, d - back, d, z0, z1, M["oak"], root)
            _slat_doors(f"{n}_c{j}", sh, w - sh, z0, z1, max(1, round(w / 0.6)), root)
    box(n + "_top", 0, w, 0.0, d, top - 0.025, top, M["oak"], root, bev=0.002)


def counter_stool(item, root):
    """Japandi counter stool: round oak seat with a linen pad, splayed legs, footrest ring."""
    W, D = frame_dims(item)
    cx, cy = W / 2, D / 2
    n = item["id"]
    seat_z = item["z"][1]
    for i in range(4):
        a = math.radians(45 + 90 * i)
        top = (cx + 0.12 * math.cos(a), cy + 0.12 * math.sin(a), seat_z - 0.03)
        foot = (cx + 0.17 * math.cos(a), cy + 0.17 * math.sin(a), 0.0)
        tube_path(f"{n}_leg{i}", [foot, top], 0.015, M["oak"], root)
    ring_r = 0.12 + 0.05 * (1 - 0.25 / seat_z)
    F_ring = tube_path(
        n + "_ring",
        arc_points(cx, cy, 0.25, ring_r + 0.01, 0, 2 * math.pi, 40),
        0.009,
        M["black_metal"],
        root,
    )
    F_ring.data.bevel_resolution = 3
    cyl(n + "_seat", cx, cy, seat_z - 0.035, seat_z - 0.005, 0.18, M["oak"], root, bev=0.006)
    pad = cyl(n + "_pad", cx, cy, seat_z - 0.006, seat_z + 0.02, 0.165, M["linen"], root)
    soften(pad, 0.01, 1)


def dining_chair(item, root, cushion=False):
    """Japandi oak chair: tapered round legs, cord-look seat, curved top rail."""
    W, D = frame_dims(item)
    cw, cd = 0.46, 0.48
    ox, oy = (W - cw) / 2, (D - cd) / 2
    n = item["id"]
    seat_z = 0.45
    legs = [
        (ox + 0.03, oy + 0.03),
        (ox + cw - 0.03, oy + 0.03),
        (ox + 0.04, oy + cd - 0.03),
        (ox + cw - 0.04, oy + cd - 0.03),
    ]
    for i, (x, y) in enumerate(legs):
        top = seat_z if i < 2 else 0.78
        cyl(f"{n}_leg{i}", x, y, 0, top, 0.016, M["oak"], root, r_top=0.013, segs=20)
    box(
        n + "_seatframe",
        ox + 0.01,
        ox + cw - 0.01,
        oy + 0.01,
        oy + cd - 0.01,
        seat_z - 0.04,
        seat_z - 0.01,
        M["oak"],
        root,
        bev=0.004,
    )
    seat = box(
        n + "_seat",
        ox + 0.025,
        ox + cw - 0.025,
        oy + 0.02,
        oy + cd - 0.02,
        seat_z - 0.012,
        seat_z + 0.02,
        M["sofa_fabric"],
        root,
    )
    soften(seat, 0.012, 1)
    if cushion:
        c = box(
            n + "_cushion",
            ox + 0.03,
            ox + cw - 0.03,
            oy + 0.03,
            oy + cd - 0.05,
            seat_z + 0.02,
            seat_z + 0.07,
            M["linen_sage"],
            root,
        )
        soften(c, 0.02, 2)
    # Stretchers
    for i, (a, b) in enumerate(((legs[0], legs[2]), (legs[1], legs[3]))):
        tube_path(f"{n}_str{i}", [(a[0], a[1], 0.16), (b[0], b[1], 0.16)], 0.008, M["oak"], root)
    # Curved top rail between the back posts
    r = 0.30  # arc ends land on the back posts, bowing 7 cm backwards in the middle
    cx, cy = ox + cw / 2, oy + cd - 0.03 - r * math.sin(math.radians(50))
    pts = arc_points(cx, cy, 0.76, r, math.radians(50), math.radians(130), 20)
    tube_path(n + "_toprail", pts, 0.022, M["oak"], root).data.bevel_resolution = 4
    tube_path(
        n + "_backslat",
        [(cx, oy + cd - 0.035, seat_z + 0.02), (cx, cy + r, 0.76)],
        0.012,
        M["oak"],
        root,
    )


def desk_chair(item, root):
    dining_chair(item, root, cushion=True)


def office_chair(item, root):
    """Ergonomic task chair: five-star base on castors, gas lift, upholstered seat, mesh back with lumbar
    pad, T-armrests. The seat front faces local -Y."""
    W, D = frame_dims(item)
    n = item["id"]
    cx, cy = W / 2, D / 2
    base, frame, fabric = M["plastic_black"], M["graphite"], M["fabric_charcoal"]
    cyl(n + "_hub", cx, cy, 0.07, 0.12, 0.045, base, root)
    for i in range(5):
        a = math.radians(90 + 72 * i)
        tx, ty = cx + 0.30 * math.cos(a), cy + 0.30 * math.sin(a)
        tube_path(f"{n}_leg{i}", [(cx, cy, 0.10), (tx, ty, 0.075)], 0.018, base, root)
        cas = cyl(f"{n}_castor{i}", 0, 0, -0.012, 0.012, 0.028, base, root, segs=20)
        cas.matrix_basis = (
            Matrix.Translation((tx, ty, 0.028))
            @ Matrix.Rotation(a, 4, "Z")
            @ Matrix.Rotation(math.pi / 2, 4, "Y")
        )
        cyl(f"{n}_castor_stem{i}", tx, ty, 0.045, 0.075, 0.008, frame, root)
    cyl(n + "_lift_cover", cx, cy, 0.12, 0.30, 0.032, base, root)
    cyl(n + "_lift", cx, cy, 0.30, 0.42, 0.022, M["chrome"], root)
    box(n + "_mech", cx - 0.13, cx + 0.13, cy - 0.14, cy + 0.12, 0.42, 0.46, frame, root, bev=0.006)
    seat = box(n + "_seat", cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.22, 0.46, 0.52, fabric, root)
    soften(seat, 0.03, 2)
    seat.modifiers.new("Puff", "CAST").factor = 0.05
    # Spine from under the seat up the back; the back leans 12 deg
    spine = [(cx, cy + 0.10, 0.44), (cx, cy + 0.30, 0.47), (cx, cy + 0.31, 0.62)]
    tube_path(n + "_spine", spine, 0.022, frame, root)
    lean = Matrix.Translation((cx, cy + 0.31, 0.60)) @ Matrix.Rotation(math.radians(-12), 4, "X")
    for part, (x0, x1, y0, y1, z0, z1), mat in (
        ("back_frame", (-0.24, 0.24, -0.012, 0.012, 0.0, 0.60), frame),
        ("back_mesh", (-0.225, 0.225, -0.016, 0.016, 0.02, 0.58), M["mesh_black"]),
    ):
        box(f"{n}_{part}", x0, x1, y0, y1, z0, z1, mat, root, bev=0.006).matrix_basis = lean
    lum = box(n + "_lumbar", -0.17, 0.17, -0.04, -0.016, 0.12, 0.22, fabric, root)
    soften(lum, 0.01, 1)
    lum.matrix_basis = lean
    for i, sx in enumerate((-1, 1)):
        x = cx + sx * 0.265
        tube_path(
            f"{n}_arm_post{i}", [(x, cy + 0.03, 0.45), (x, cy + 0.05, 0.68)], 0.014, frame, root
        )
        box(
            f"{n}_arm_pad{i}",
            x - 0.04,
            x + 0.04,
            cy - 0.10,
            cy + 0.15,
            0.68,
            0.705,
            base,
            root,
            bev=0.01,
        )


# ---------------------------------------------------------------- living


def sofa(item, root):
    """Sofa along the back (y = d) with an optional chaise on one end. body_depth is the seat depth of the
    main body (default: the whole item); chaise_w is the chaise's width along the wall and chaise_end
    ("south", the low-x end, or "north") says where it is. The chaise runs the whole depth d, so the item's
    depth includes it."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    fabric = M[p.get("fabric", "sofa_fabric")]
    ds = p.get("body_depth", d)
    yo = (
        d - ds
    )  # the main body starts yo behind the front; the chaise fills the strip in front of it
    cw = p.get("chaise_w", 0.0)
    north = p.get("chaise_end", "south") == "north"
    arm_w, leg_h = 0.16, 0.08
    base_top = 0.36

    def mx(a, b):
        """x range on the chaise end of the item (a, b measured from that end)."""
        return (w - b, w - a) if north else (a, b)

    legs = [(0.06, yo + 0.08), (w - 0.06, yo + 0.08), (0.06, d - 0.08), (w - 0.06, d - 0.08)]
    if cw:
        legs += [(w - 0.06 if north else 0.06, 0.08), (w - cw + 0.06 if north else cw - 0.06, 0.08)]
    for i, (x, y) in enumerate(legs):
        cyl(f"{n}_leg{i}", x, y, 0, leg_h + 0.01, 0.022, M["oak"], root, r_top=0.018)
    soften(box(n + "_base", 0.0, w, yo + 0.02, d, leg_h, base_top, fabric, root), 0.03, 1)
    if cw:  # the arm on the chaise end is dropped
        arms = [(0.0, arm_w)] if north else [(w - arm_w, w)]
    else:
        arms = [(0.0, arm_w), (w - arm_w, w)]
    for i, (a, b) in enumerate(arms):
        soften(box(f"{n}_arm{i}", a, b, yo, d, leg_h, 0.62, fabric, root), 0.05, 2)
    sx0, sx1 = (arm_w, w - (cw or arm_w)) if north else (cw or arm_w, w - arm_w)
    if cw:
        a, b = mx(0.0, cw)
        soften(
            box(n + "_chaise_base", a, b, 0.0, yo + 0.02, leg_h, base_top, fabric, root), 0.03, 1
        )
        a, b = mx(0.004, cw - 0.004)
        ch = box(n + "_chaise", a, b, 0.0, d - 0.17, base_top - 0.01, base_top + 0.15, fabric, root)
        soften(ch, 0.05, 2)
        ch.modifiers.new("Puff", "CAST").factor = 0.08
    bx0, bx1 = (arm_w, w) if (north and cw) else (0.0 if cw else arm_w, w - arm_w)
    soften(
        box(n + "_backframe", bx0, bx1, d - 0.18, d, base_top - 0.02, 0.62, fabric, root), 0.04, 2
    )
    inner = sx1 - sx0
    k = max(2, round(inner / 0.8))
    for i in range(k):
        a = sx0 + inner * i / k + 0.004
        b = sx0 + inner * (i + 1) / k - 0.004
        s = box(
            f"{n}_seat{i}",
            a,
            b,
            yo + 0.02,
            d - 0.17,
            base_top - 0.01,
            base_top + 0.15,
            fabric,
            root,
        )
        soften(s, 0.05, 2)
        s.modifiers.new("Puff", "CAST").factor = 0.08
        bc = box_c(
            f"{n}_backcush{i}",
            b - a,
            0.20,
            0.44,
            ((a + b) / 2, d - 0.27, base_top + 0.33),
            fabric,
            root,
        )
        soften(bc, 0.07, 2)
        bc.rotation_euler.x = math.radians(-9)
    # Throw pillows and a draped throw over the arm
    for i, (x, mat, ang) in enumerate(
        ((sx0 + 0.28, M["sofa_fabric"], 12), (sx1 - 0.30, M["linen"], -10))
    ):
        pl = pillow(f"{n}_pillow{i}", 0.46, 0.46, 0.14, mat, root)
        pl.location = (x, d - 0.47, base_top + 0.38)
        pl.rotation_euler = (math.radians(-20), math.radians(ang), 0)
        settle(pl, base_top + 0.15, sink=0.025)
    throw = drape(
        n + "_throw",
        0.0,
        arm_w,
        yo + 0.10,
        d - 0.25,
        0.625,
        M["linen_green"],
        root,
        over_x=(0.10, 0.30),
        over_y=(0.0, 0.0),
        thickness=0.012,
    )
    throw.location.x = 0.0 if north else w - arm_w


def pillow(name, sx, sy, thick, mat, parent):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, thick, sy), verts=bm.verts)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=6, use_grid_fill=True)
    # Pinch the edges: the pillow is thick in the middle, flat at the seams
    for v in bm.verts:
        fx, fz = abs(v.co.x) / (sx / 2), abs(v.co.z) / (sy / 2)
        v.co.y *= max(0.15, 1 - max(fx, fz) ** 3)
    obj = mesh_obj(name, bm, mat, parent, smooth=True)
    s = obj.modifiers.new("Subsurf", "SUBSURF")
    s.levels = s.render_levels = 2
    return obj


def drape(
    name,
    x0,
    x1,
    y0,
    y1,
    z_top,
    mat,
    parent,
    over_x=(0.25, 0.25),
    over_y=(0.15, 0.0),
    thickness=0.03,
    res=0.025,
    wrinkle=0.012,
):
    """Fabric laid over a box top [x0,x1]x[y0,y1] at z_top, hanging over the edges.

    over_x / over_y are the hang lengths on the (low, high) sides. The sheet is laid flat, then any part beyond
    the top bends down with a small radius, so it reads like a duvet or a throw.
    """
    gx0, gx1 = x0 - over_x[0], x1 + over_x[1]
    gy0, gy1 = y0 - over_y[0], y1 + over_y[1]
    nx, ny = max(2, int((gx1 - gx0) / res)), max(2, int((gy1 - gy0) / res))
    bm = bmesh.new()
    rows = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = gx0 + (gx1 - gx0) * i / nx
            y = gy0 + (gy1 - gy0) * j / ny
            dz = 0.0
            r = 0.04  # bend radius
            if x < x0:
                s = x0 - x
                ang = min(s / r, math.pi / 2)
                x, dz = (
                    x0 - r * math.sin(ang) - max(0, s - r * math.pi / 2) * 0.03,
                    r * (1 - math.cos(ang)) + max(0, s - r * math.pi / 2),
                )
            elif x > x1:
                s = x - x1
                ang = min(s / r, math.pi / 2)
                x, dz = (
                    x1 + r * math.sin(ang) + max(0, s - r * math.pi / 2) * 0.03,
                    r * (1 - math.cos(ang)) + max(0, s - r * math.pi / 2),
                )
            if y < y0:
                s = y0 - y
                ang = min(s / r, math.pi / 2)
                y = y0 - r * math.sin(ang) - max(0, s - r * math.pi / 2) * 0.03
                dz = max(dz, r * (1 - math.cos(ang)) + max(0, s - r * math.pi / 2))
            elif y > y1:
                s = y - y1
                ang = min(s / r, math.pi / 2)
                y = y1 + r * math.sin(ang) + max(0, s - r * math.pi / 2) * 0.03
                dz = max(dz, r * (1 - math.cos(ang)) + max(0, s - r * math.pi / 2))
            row.append(bm.verts.new((x, y, z_top - dz)))
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    obj = mesh_obj(name, bm, mat, parent, smooth=True)
    tex = bpy.data.textures.new(name + "_wrinkles", "CLOUDS")
    tex.noise_scale = 0.12
    disp = obj.modifiers.new("Wrinkles", "DISPLACE")
    disp.texture = tex
    disp.strength = wrinkle
    disp.mid_level = 0.5
    sol = obj.modifiers.new("Thickness", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = 1.0
    sub = obj.modifiers.new("Subsurf", "SUBSURF")
    sub.levels = sub.render_levels = 1
    return obj


def ottoman(item, root):
    w, d = frame_dims(item)
    mat = M[item.get("params", {}).get("material", "boucle")]
    if item.get("params", {}).get("round"):
        # Drum pouf: a soft cylinder with a rounded top edge
        o = cyl(
            item["id"] + "_body",
            w / 2,
            d / 2,
            0.0,
            item["z"][1],
            min(w, d) / 2,
            mat,
            root,
            segs=64,
        )
        bevel(o, 0.06, 4, angle=60)
        return
    o = box(item["id"] + "_body", 0, w, 0, d, 0.0, item["z"][1], mat, root)
    soften(o, 0.07, 2)
    o.modifiers.new("Puff", "CAST").factor = 0.06


def rug(item, root):
    w, d = frame_dims(item)
    box(item["id"], 0, w, 0, d, 0.0005, item["z"][1], M["rug"], root, bev=0.004, seg=3)


def tv_console(item, root):
    w, d = frame_dims(item)
    n = item["id"]
    top = item["z"][1]
    for i, x in enumerate((0.05, w - 0.05)):
        for j, y in enumerate((0.05, d - 0.05)):
            cyl(f"{n}_leg{i}{j}", x, y, 0, 0.12, 0.012, M["black_metal"], root)
    box(n + "_body", 0, w, 0, d, 0.12, top, M["oak"], root, bev=0.003)
    k = item.get("params", {}).get("doors", 4)
    for i in range(k):
        a, b = w * i / k, w * (i + 1) / k
        box(
            f"{n}_front{i}",
            a + GAP,
            b - GAP,
            -0.003,
            0.0,
            0.12 + 0.02,
            top - 0.02,
            M["oak"],
            root,
            bev=0.001,
        )
        # Vertical slat grooves for texture
        for s in range(1, 8):
            x = a + (b - a) * s / 8
            box(
                f"{n}_slat{i}_{s}",
                x - 0.0015,
                x + 0.0015,
                -0.0045,
                -0.003,
                0.14,
                top - 0.02,
                M["oak_dark"],
                root,
            )


def _slat_doors(n, x0, x1, z0, z1, k, root):
    """k oak doors with vertical smoked-oak grooves, front face at y = 0, carcass behind from y = 0.02."""
    for i in range(k):
        a, b = x0 + (x1 - x0) * i / k, x0 + (x1 - x0) * (i + 1) / k
        box(
            f"{n}_door{i}",
            a + GAP,
            b - GAP,
            0.0,
            0.02,
            z0 + GAP,
            z1 - GAP,
            M["oak"],
            root,
            bev=0.001,
        )
        for s in range(1, 8):
            x = a + (b - a) * s / 8
            box(
                f"{n}_slat{i}_{s}",
                x - 0.0015,
                x + 0.0015,
                -0.0015,
                0.0,
                z0 + 0.02,
                z1 - 0.02,
                M["oak_dark"],
                root,
            )


def media_wall(item, root):
    """Built-in oak TV wall: a tall tower at each end (closed cupboard below, open niches above with forest
    green backs), a wall-hung slatted cabinet under the TV, a closed bridge cabinet over it and a green
    panel behind the screen."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    tw, top = p.get("tower_width", 0.50), item["z"][1]
    c0, c1 = p.get("console_z", (0.20, 0.55))
    bz = p.get("bridge_z0", 1.90)
    sh, back = 0.019, 0.012
    for t, (a, b) in enumerate(((0.0, tw), (w - tw, w))):
        tn = f"{n}_tower{t}"
        box(tn + "_plinth", a + sh, b - sh, 0.05, d - back, 0.0, 0.06, M["plastic_black"], root)
        box(tn + "_sideL", a, a + sh, 0.0, d, 0.0, top - 0.025, M["oak"], root, bev=0.001)
        box(tn + "_sideR", b - sh, b, 0.0, d, 0.0, top - 0.025, M["oak"], root, bev=0.001)
        box(tn + "_top", a, b, 0.0, d, top - 0.025, top, M["oak"], root, bev=0.002)
        box(tn + "_carcass", a + sh, b - sh, 0.02, d, 0.06, 0.90, M["oak"], root)
        _slat_doors(tn, a + sh, b - sh, 0.06, 0.90, 1, root)
        box(tn + "_back", a + sh, b - sh, d - back, d, 0.90, top - 0.025, M["paint_green"], root)
        for j, z in enumerate(z for z in (0.90, 1.35, 1.80, 2.25, 2.70) if z < top - 0.2):
            box(
                f"{tn}_shelf{j}",
                a + sh,
                b - sh,
                0.0,
                d - back,
                z,
                z + 0.022,
                M["oak"],
                root,
                bev=0.001,
            )
    m0, m1 = tw, w - tw
    box(n + "_console", m0, m1, 0.02, d, c0, c1, M["oak"], root)
    _slat_doors(n + "_console", m0, m1, c0, c1, 3, root)
    box(n + "_bridge", m0, m1, 0.02, d, bz, top, M["oak"], root)
    for i in range(3):
        a, b = m0 + (m1 - m0) * i / 3, m0 + (m1 - m0) * (i + 1) / 3
        box(
            f"{n}_bridge_door{i}",
            a + GAP,
            b - GAP,
            0.0,
            0.02,
            bz + GAP,
            top - GAP,
            M["oak"],
            root,
            bev=0.001,
        )
    box(n + "_panel", m0, m1, d - back, d, c1, bz, M["paint_green"], root)
    box(n + "_led", m0 + 0.02, m1 - 0.02, 0.06, 0.08, bz - 0.003, bz, M["led"], root)


def bistro_table(item, root):
    """Round balcony table: smoked-oak slatted top on a graphite pedestal."""
    w, d = frame_dims(item)
    n, top = item["id"], item["z"][1]
    cx, cy, r = w / 2, d / 2, min(w, d) / 2
    cyl(n + "_foot", cx, cy, 0.0, 0.02, 0.22, M["graphite"], root, bev=0.004)
    cyl(n + "_stem", cx, cy, 0.02, top - 0.03, 0.022, M["graphite"], root)
    cyl(n + "_top", cx, cy, top - 0.03, top, r, M["oak_dark"], root, segs=64, bev=0.004)


def bistro_chair(item, root):
    """Folding balcony chair: graphite tube frame, smoked-oak slats for the seat and back."""
    W, D = frame_dims(item)
    cw, cd = 0.42, 0.44
    ox, oy = (W - cw) / 2, (D - cd) / 2
    n, seat_z = item["id"], 0.45
    for i, x in enumerate((ox + 0.02, ox + cw - 0.02)):
        tube_path(
            f"{n}_front{i}",
            [(x, oy + 0.02, 0.0), (x, oy + 0.04, seat_z)],
            0.011,
            M["graphite"],
            root,
        )
        tube_path(
            f"{n}_back{i}",
            [(x, oy + cd - 0.06, 0.0), (x, oy + cd, 0.86)],
            0.011,
            M["graphite"],
            root,
        )
        tube_path(
            f"{n}_rail{i}",
            [(x, oy + 0.04, seat_z - 0.02), (x, oy + cd - 0.03, seat_z - 0.02)],
            0.009,
            M["graphite"],
            root,
        )
    for k in range(5):
        y = oy + 0.03 + k * 0.075
        box(
            f"{n}_seat{k}",
            ox + 0.005,
            ox + cw - 0.005,
            y,
            y + 0.062,
            seat_z - 0.01,
            seat_z + 0.01,
            M["oak_dark"],
            root,
            bev=0.003,
        )
    for k, z in enumerate((0.62, 0.71, 0.80)):
        yb = oy + cd - 0.06 + 0.06 * (z / 0.86)
        box(
            f"{n}_backslat{k}",
            ox + 0.0,
            ox + cw,
            yb + 0.012,
            yb + 0.030,
            z - 0.035,
            z + 0.035,
            M["oak_dark"],
            root,
            bev=0.003,
        )


def tv(item, root):
    w, d = frame_dims(item)
    z0, z1 = item["z"]
    box(item["id"] + "_body", 0, w, 0.004, d, z0, z1, M["plastic_black"], root, bev=0.002)
    box(
        item["id"] + "_screen",
        0.006,
        w - 0.006,
        0.0,
        0.004,
        z0 + 0.006,
        z1 - 0.006,
        M["screen_off"],
        root,
    )


def floor_lamp(item, root):
    w, d = frame_dims(item)
    cx, cy = w / 2, d / 2
    n = item["id"]
    cyl(n + "_base", cx, cy, 0, 0.025, 0.13, M["oak"], root, bev=0.004)
    cyl(n + "_pole", cx, cy, 0.025, 1.12, 0.008, M["black_metal"], root)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=48, radius1=0.16, radius2=0.16, depth=0.45)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(cx, cy, 1.10 + 0.225))
    shade = mesh_obj(n + "_shade", bm, M["paper"], root, smooth=True)
    sol = shade.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.002
    # Paper-lantern ribs
    for k in range(9):
        z = 1.10 + 0.45 * k / 8
        tube_path(
            f"{n}_rib{k}",
            arc_points(cx, cy, z, 0.1605, 0, 2 * math.pi, 40),
            0.0012,
            M["paper"],
            root,
        )
    add_point_light(n + "_light", (cx, cy, 1.32), root, power=25, radius=0.04)


def add_point_light(name, loc, parent, power=40.0, radius=0.03, color=(1.0, 0.80, 0.58)):
    """A lamp's bulb. Lights carry role='lamp' so build_interior can switch day/evening."""
    ld = bpy.data.lights.new(name, "POINT")
    ld.energy = power
    ld.shadow_soft_size = radius
    ld.color = color
    obj = bpy.data.objects.new(name, ld)
    obj.location = loc
    obj["role"] = "lamp"
    obj["power_on"] = power
    return _link(obj, parent)


def table_lamp(name, x, y, z, parent):
    """Small ceramic table lamp with a linen drum shade; sits on a surface at height z."""
    cyl(name + "_base", x, y, z, z + 0.20, 0.06, M["ceramic"], parent, r_top=0.045)
    cyl(name + "_neck", x, y, z + 0.20, z + 0.27, 0.008, M["steel"], parent)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=48, radius1=0.13, radius2=0.11, depth=0.18)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(x, y, z + 0.33))
    shade = mesh_obj(name + "_shade", bm, M["paper"], parent, smooth=True)
    shade.modifiers.new("Solidify", "SOLIDIFY").thickness = 0.002
    add_point_light(name + "_light", (x, y, z + 0.30), parent, power=15, radius=0.03)


# ---------------------------------------------------------------- storage


def wardrobe(item, root):
    """Built-in wardrobe, hinged or sliding doors. Taller than 2.45 m it gets a row of top-box doors above
    split_z, as built-ins do when they run up to a high ceiling; a filler closes any gap to the ceiling.
    Sliding doors are oak, or full-height mirror glass with `mirror` (`"smoked"` for a bronze-grey tint)."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    top = item["z"][1]
    W = M["front_white"]
    box(n + "_plinth", 0, w, 0.04, d - 0.02, 0, 0.06, M["plastic_black"], root)
    # Sliding fronts run in the gap in front of the carcass
    cy0 = 0.05 if p.get("sliding") else 0.025
    box(n + "_carcass", 0, w, cy0, d, 0.06, top, W, root)
    if CEIL - top > 0.005:
        box(n + "_filler", 0, w, 0.04, d, top, CEIL, W, root)
    split = p.get("split_z", 2.25) if top > 2.45 else top
    if p.get("sliding") and p.get("mirror"):
        split = top  # mirror fronts run the full height, no top boxes
    k = p.get("doors", 2)
    if p.get("sliding"):
        half = w / 2 + 0.02
        door = M["oak"]
        if p.get("mirror"):
            door = M["mirror_smoked"] if p["mirror"] == "smoked" else M["mirror"]
        box(n + "_track", 0, w, 0.0, 0.05, split - 0.04, split, W, root)
        box(
            n + "_slide_back",
            0.0,
            half,
            0.026,
            0.045,
            0.065,
            split - 0.045,
            door,
            root,
            bev=0.002,
        )
        box(
            n + "_slide_front",
            w - half,
            w,
            0.0,
            0.019,
            0.065,
            split - 0.045,
            door,
            root,
            bev=0.002,
        )
        for i, x in enumerate((half - 0.06, w - half + 0.04)):
            box(
                f"{n}_grip{i}",
                x - 0.012,
                x + 0.012,
                -0.004,
                0.0 if i else 0.026,
                0.95,
                1.35,
                M["oak_dark"],
                root,
            )
        k = max(k, round(w / 0.5))
    else:
        for i in range(k):
            a, b = w * i / k, w * (i + 1) / k
            box(
                f"{n}_door{i}",
                a + GAP,
                b - GAP,
                0.006,
                0.025,
                0.065,
                split - GAP,
                W,
                root,
                bev=0.0015,
            )
            px = b - 0.05 if i % 2 == 0 else a + 0.05
            box(
                f"{n}_pull{i}",
                px - 0.012,
                px + 0.012,
                -0.012,
                0.006,
                0.95,
                1.30,
                M["oak"],
                root,
                bev=0.003,
            )
    if top - split > 0.1:
        for i in range(k):
            a, b = w * i / k, w * (i + 1) / k
            box(
                f"{n}_topdoor{i}",
                a + GAP,
                b - GAP,
                0.006,
                0.025,
                split + GAP,
                top - GAP,
                W,
                root,
                bev=0.0015,
            )


def l_wardrobe(item, root):
    """L-shaped built-in wardrobe for a hall corner, built in world coordinates. The main run stands on the
    footprint's ymin wall with hinged doors facing +Y; the corner behind the return is reached through the
    main run. The return runs along the xmax wall with its door facing -X: an open shoe niche at the
    bottom, a cupboard door above it. Both legs carry top boxes from split_z up to the top."""
    x0, x1, y0, y1 = item["footprint"]
    p = item.get("params", {})
    n = item["id"]
    top = item["z"][1]
    dm, dr = p.get("main_depth", 0.60), p.get("return_depth", 0.40)
    split = p.get("split_z", 2.25)
    W, oak = M["front_white"], M["oak"]
    xr, ym = x1 - dr, y0 + dm  # front planes of the return and the main run
    # Main run
    box(n + "_main_plinth", x0, x1, y0 + 0.02, ym - 0.04, 0, 0.06, M["plastic_black"], root)
    box(n + "_main_carcass", x0, x1, y0, ym - 0.025, 0.06, top, W, root)
    k = max(1, round((xr - x0) / 0.45))
    for row, (za, zb) in enumerate(((0.065, split), (split, top))):
        for i in range(k):
            a, b = x0 + (xr - x0) * i / k, x0 + (xr - x0) * (i + 1) / k
            box(
                f"{n}_main_door{row}_{i}",
                a + GAP,
                b - GAP,
                ym - 0.025,
                ym - 0.006,
                za + GAP,
                zb - GAP,
                W,
                root,
                bev=0.0015,
            )
            if row == 0:
                px = b - 0.05 if i % 2 == 0 else a + 0.05
                box(
                    f"{n}_main_pull{i}",
                    px - 0.012,
                    px + 0.012,
                    ym - 0.006,
                    ym + 0.012,
                    0.95,
                    1.30,
                    oak,
                    root,
                    bev=0.003,
                )
    box(n + "_corner_panel", xr, x1, ym - 0.025, ym, 0.06, top, W, root)
    # Return
    box(n + "_ret_plinth", xr + 0.04, x1, ym, y1 - 0.02, 0, 0.06, M["plastic_black"], root)
    box(n + "_ret_carcass", xr + 0.025, x1, ym, y1, 0.06, top, W, root)
    niche = p.get("shoe_niche", 0.42)
    box(
        n + "_ret_niche_back", xr + 0.025, xr + 0.04, ym + 0.019, y1 - 0.019, 0.06, niche, oak, root
    )
    box(
        n + "_ret_niche_shelf",
        xr + 0.006,
        x1 - 0.02,
        ym + 0.019,
        y1 - 0.019,
        0.22,
        0.238,
        oak,
        root,
        bev=0.001,
    )
    box(
        n + "_ret_niche_top",
        xr + 0.006,
        xr + 0.04,
        ym + 0.019,
        y1 - 0.019,
        niche - 0.018,
        niche,
        oak,
        root,
    )
    for i, (za, zb) in enumerate(((niche, split), (split, top))):
        box(
            f"{n}_ret_door{i}",
            xr + 0.006,
            xr + 0.025,
            ym + GAP,
            y1 - GAP,
            za + GAP,
            zb - GAP,
            W,
            root,
            bev=0.0015,
        )
    box(
        n + "_ret_pull",
        xr - 0.012,
        xr + 0.006,
        y1 - 0.062,
        y1 - 0.038,
        0.95,
        1.30,
        oak,
        root,
        bev=0.003,
    )
    if CEIL - top > 0.005:
        box(n + "_filler_main", x0, x1, y0, ym - 0.04, top, CEIL, W, root)
        box(n + "_filler_ret", xr + 0.04, x1, ym - 0.04, y1, top, CEIL, W, root)


def wall_cabinet(item, root):
    """Wall-hung cupboard with flat doors ('front' material, default oak) and an optional open shelf
    'shelf_below' metres under it."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    z0, z1 = item["z"]
    wood = M[p.get("wood", "oak")]
    front = M[p.get("front", "oak")]
    box(n + "_carcass", 0, w, 0.02, d, z0, z1, wood, root, bev=0.002)
    k = p.get("doors", 2)
    for i in range(k):
        a, b = w * i / k, w * (i + 1) / k
        box(
            f"{n}_door{i}", a + GAP, b - GAP, 0.0, 0.02, z0 + GAP, z1 - GAP, front, root, bev=0.0015
        )
        px = b - 0.035 if i % 2 == 0 else a + 0.035
        box(
            f"{n}_pull{i}",
            px - 0.006,
            px + 0.006,
            -0.014,
            0.0,
            z0 + 0.03,
            z0 + 0.15,
            wood,
            root,
            bev=0.002,
        )
    if "shelf_below" in p:
        zs = z0 - p["shelf_below"]
        box(n + "_shelf", 0, w, 0.02, d, zs - 0.025, zs, wood, root, bev=0.002)


def art_print(item, root):
    """Framed print: slim oak frame, warm-white mount, the image (assets/images/<params.image>.jpg)
    centre-cropped to the opening. Hangs flat on the wall behind it (local y = d)."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    z0, z1 = item["z"]
    fw, mount = p.get("frame", 0.02), p.get("mount", 0.05)
    oak = M[p.get("frame_material", "oak")]
    box(n + "_frame_l", 0, fw, 0, d, z0, z1, oak, root, bev=0.002)
    box(n + "_frame_r", w - fw, w, 0, d, z0, z1, oak, root, bev=0.002)
    box(n + "_frame_b", fw, w - fw, 0, d, z0, z0 + fw, oak, root, bev=0.002)
    box(n + "_frame_t", fw, w - fw, 0, d, z1 - fw, z1, oak, root, bev=0.002)
    box(n + "_mount", fw, w - fw, 0.008, d, z0 + fw, z1 - fw, M["paper_mount"], root)
    ax0, ax1, az0, az1 = fw + mount, w - fw - mount, z0 + fw + mount, z1 - fw - mount
    img = bpy.data.images.load(str(IMAGES / f"{p['image']}.jpg"), check_existing=True)
    iw, ih = img.size
    a, ai = (ax1 - ax0) / (az1 - az0), iw / ih
    u0, u1, v0, v1 = 0.0, 1.0, 0.0, 1.0
    if ai > a:
        u0, u1 = 0.5 - a / ai / 2, 0.5 + a / ai / 2
    else:
        v0, v1 = 0.5 - ai / a / 2, 0.5 + ai / a / 2
    m = bpy.data.materials.get("Print_" + p["image"])
    if m is None:
        m = bpy.data.materials.new("Print_" + p["image"])
        m.use_nodes = True
        nt = m.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        bsdf = nt.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 0.55
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new()
    y = 0.0075
    vs = [bm.verts.new(c) for c in ((ax0, y, az0), (ax1, y, az0), (ax1, y, az1), (ax0, y, az1))]
    f = bm.faces.new(vs)
    for loop, co in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1)), strict=True):
        loop[uv].uv = co
    mesh_obj(n + "_print", bm, m, root)


def floating_shelf(item, root):
    w, d = frame_dims(item)
    z0, z1 = item["z"]
    box(item["id"], 0, w, 0, d, z0, z1 + 0.0, M["oak"], root, bev=0.002)


def mirror(item, root):
    w, d = frame_dims(item)
    z0, z1 = item["z"]
    box(item["id"] + "_frame", 0, w, 0.002, d, z0, z1, M["oak"], root, bev=0.003)
    box(item["id"] + "_glass", 0.02, w - 0.02, 0.0, 0.004, z0 + 0.02, z1 - 0.02, M["mirror"], root)


# ---------------------------------------------------------------- bedroom


def bed(item, root):
    """Low oak platform bed with an upholstered linen headboard, duvet, pillows and a throw."""
    w, d = frame_dims(item)  # facing -x: width 1.6 along world Y, depth 2.0 along world X
    n = item["id"]
    box(n + "_plinth", 0.08, w - 0.08, 0.10, d - 0.10, 0, 0.12, M["plastic_black"], root)
    box(
        n + "_frame", -0.02, w + 0.02, -0.02, d - 0.06, 0.12, 0.30, M["oak"], root, bev=0.004, seg=3
    )
    hb = box(n + "_headboard", -0.03, w + 0.03, d - 0.08, d, 0.24, item["z"][1], M["linen"], root)
    soften(hb, 0.025, 2)
    mt = box(n + "_mattress", 0.0, w, 0.0, d - 0.10, 0.30, 0.52, M["mattress"], root)
    soften(mt, 0.03, 1)
    top = 0.52
    # Duvet over the lower ~3/4, hanging over both sides and the foot, with a turned-down band
    drape(
        n + "_duvet",
        0.0,
        w,
        0.0,
        d - 0.62,
        top,
        M["cotton_white"],
        root,
        over_x=(0.24, 0.24),
        over_y=(0.18, 0.0),
        thickness=0.045,
        wrinkle=0.015,
    )
    band = box(
        n + "_duvet_fold",
        -0.02,
        w + 0.02,
        d - 0.80,
        d - 0.60,
        top + 0.035,
        top + 0.085,
        M["cotton_white"],
        root,
    )
    soften(band, 0.025, 2)
    # Sheet visible at the head end
    box(
        n + "_sheet",
        -0.005,
        w + 0.005,
        d - 0.62,
        d - 0.10,
        top - 0.01,
        top + 0.004,
        M["cotton_white"],
        root,
    )
    # Pillows: two sleeping pillows against the headboard, two decorative in front
    for i, x in enumerate((w * 0.26, w * 0.74)):
        p = pillow(f"{n}_pillow{i}", 0.66, 0.48, 0.17, M["cotton_white"], root)
        p.location = (x, d - 0.26, top + 0.20)
        p.rotation_euler = (math.radians(-68), 0, math.radians(2 - 4 * i))
        settle(p, top + 0.004, sink=0.02)
    for i, (x, mat) in enumerate(((w * 0.36, M["linen_sage"]), (w * 0.64, M["linen"]))):
        p = pillow(f"{n}_cushion{i}", 0.45, 0.45, 0.14, mat, root)
        p.location = (x, d - 0.48, top + 0.18)
        p.rotation_euler = (math.radians(-22), 0, math.radians(-4 + 8 * i))
        settle(p, top + 0.004, sink=0.015)
    # Throw across the foot
    drape(
        n + "_throw",
        -0.05,
        w + 0.05,
        0.10,
        0.42,
        top + 0.055,
        M["linen_sage"],
        root,
        over_x=(0.30, 0.30),
        over_y=(0.0, 0.0),
        thickness=0.012,
        wrinkle=0.01,
    )


def standing_desk(item, root):
    """Electric sit-stand desk: oak top on a black two-column frame. Two 27-inch monitors on a dual arm,
    angled in, a small-form-factor PC standing on the desk, keyboard and mouse."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    top = item["z"][1]
    bm_, bk = M["black_metal"], M["plastic_black"]
    box(n + "_top", 0, w, 0, d, top - 0.025, top, M["oak"], root, bev=0.003, seg=3)
    for i, x in enumerate((0.12, w - 0.12)):
        box(f"{n}_foot{i}", x - 0.035, x + 0.035, 0.03, d - 0.03, 0, 0.035, bm_, root, bev=0.004)
        box(
            f"{n}_col_low{i}",
            x - 0.04,
            x + 0.04,
            d / 2 - 0.03,
            d / 2 + 0.03,
            0.035,
            0.42,
            bm_,
            root,
            bev=0.003,
        )
        box(
            f"{n}_col_up{i}",
            x - 0.033,
            x + 0.033,
            d / 2 - 0.024,
            d / 2 + 0.024,
            0.42,
            top - 0.05,
            bm_,
            root,
            bev=0.002,
        )
        box(
            f"{n}_arm{i}",
            x - 0.03,
            x + 0.03,
            0.06,
            d - 0.06,
            top - 0.055,
            top - 0.025,
            bm_,
            root,
            bev=0.002,
        )
    box(
        n + "_beam", 0.12, w - 0.12, d / 2 - 0.02, d / 2 + 0.02, top - 0.075, top - 0.035, bm_, root
    )
    box(n + "_panel", 0.18, 0.30, 0.015, 0.05, top - 0.045, top - 0.025, bk, root, bev=0.003)
    # Dual monitor arm clamped to the back edge
    mx = p.get("monitors_x", w / 2)
    py = d - 0.05
    box(
        n + "_clamp",
        mx - 0.04,
        mx + 0.04,
        d - 0.09,
        d - 0.01,
        top,
        top + 0.03,
        bm_,
        root,
        bev=0.004,
    )
    cyl(n + "_pole", mx, py, top + 0.03, top + 0.48, 0.017, bm_, root)
    sw, sh = 0.615, 0.365  # 27-inch 16:9
    zc = top + 0.37
    for i, sgn in enumerate((-1, 1)):
        ang = math.radians(-sgn * p.get("monitor_angle", 12))
        cx = mx + sgn * (sw / 2 * math.cos(ang) + 0.006)
        cy = d - 0.22 - sw / 2 * abs(math.sin(ang))
        mon = empty(f"{n}_monitor{i}", root.users_collection[0])
        mon.parent = root
        mon.matrix_basis = Matrix.Translation((cx, cy, zc)) @ Matrix.Rotation(ang, 4, "Z")
        box(
            f"{n}_mon{i}_body",
            -sw / 2,
            sw / 2,
            0.0,
            0.012,
            -sh / 2 - 0.008,
            sh / 2 + 0.004,
            bk,
            mon,
            bev=0.003,
        )
        box(f"{n}_mon{i}_back", -0.20, 0.20, 0.012, 0.045, -0.13, 0.13, bk, mon, bev=0.01)
        box(
            f"{n}_mon{i}_screen",
            -sw / 2 + 0.006,
            sw / 2 - 0.006,
            -0.0005,
            0.0,
            -sh / 2 + 0.004,
            sh / 2 - 0.002,
            M["screen_off"],
            mon,
        )
        # Arm from the pole to the back of the monitor (world-space points in the desk frame)
        back = mon.matrix_basis @ Matrix.Translation((0, 0.045, 0))
        bx, by = back.translation.x, back.translation.y
        tube_path(
            f"{n}_arm_link{i}",
            [(mx, py, top + 0.40), ((mx + bx) / 2, py - 0.02, top + 0.40), (bx, by, zc)],
            0.014,
            bm_,
            root,
        )
    # Small-form-factor PC (~10 l), standing at the back right
    px0, px1 = p.get("pc_x", (w - 0.17, w - 0.05))
    box(n + "_pc", px0, px1, d - 0.40, d - 0.07, top, top + 0.27, M["graphite"], root, bev=0.006)
    for k in range(7):
        z = top + 0.06 + k * 0.025
        box(f"{n}_pc_vent{k}", px0 + 0.02, px1 - 0.02, d - 0.4015, d - 0.40, z, z + 0.012, bk, root)
    cyl(n + "_pc_button", 0, 0, -0.002, 0.0, 0.008, M["steel"], root).location = (
        (px0 + px1) / 2,
        d - 0.40,
        top + 0.24,
    )
    # Keyboard and mouse
    kx = mx
    box(
        n + "_keyboard",
        kx - 0.18,
        kx + 0.18,
        0.12,
        0.25,
        top,
        top + 0.012,
        M["plastic_white"],
        root,
        bev=0.003,
    )
    mouse = box(
        n + "_mouse", kx + 0.27, kx + 0.33, 0.14, 0.24, top, top + 0.03, M["plastic_white"], root
    )
    soften(mouse, 0.012, 2)


# ---------------------------------------------------------------- bathroom


def walkin_shower(item, root):
    """Low stone-resin tray (the drain sits above the slab, see the developer note), fixed glass, rain head."""
    p = item.get("params", {})
    x0, x1, y0, y1 = item["footprint"]
    n = item["id"]
    coll_parent = root
    # This generator works in world coordinates: the root stays at the origin with no rotation.
    box(n + "_tray", x0, x1, y0, y1, 0.0, 0.035, M["hex_floor"], coll_parent, bev=0.003)
    box(
        n + "_drain",
        x0 + 0.15,
        x1 - 0.15,
        y1 - 0.09,
        y1 - 0.05,
        0.035,
        0.037,
        M["steel"],
        coll_parent,
    )
    gx = p.get("glass_from_x", x1 - 1.0)
    box(n + "_glass", gx, x1, y0 + 0.01, y0 + 0.018, 0.035, 2.00, M["glass"], coll_parent)
    box(
        n + "_profile",
        x1 - 0.02,
        x1,
        y0 + 0.004,
        y0 + 0.024,
        0.035,
        2.00,
        M["black_metal"],
        coll_parent,
    )
    box(
        n + "_stabiliser",
        gx + 0.01,
        gx + 0.03,
        y0 + 0.012,
        y1,
        1.98,
        2.00,
        M["black_metal"],
        coll_parent,
    )
    hx, hy = p.get("head_at", ((x0 + x1) / 2, (y0 + y1) / 2))
    # Rain head at 2.20 m on a wall arm from the back wall (the ceiling is 2.95 m, too high for a ceiling arm)
    hz = p.get("head_z", 2.20)
    tube_path(
        n + "_arm",
        [(hx, y1, hz + 0.03), (hx, hy, hz + 0.03), (hx, hy, hz + 0.015)],
        0.011,
        M["black_metal"],
        coll_parent,
    )
    box(
        n + "_arm_rose",
        hx - 0.03,
        hx + 0.03,
        y1 - 0.012,
        y1,
        hz,
        hz + 0.06,
        M["black_metal"],
        coll_parent,
        bev=0.004,
    )
    box(
        n + "_head",
        hx - 0.15,
        hx + 0.15,
        hy - 0.15,
        hy + 0.15,
        hz,
        hz + 0.015,
        M["black_metal"],
        coll_parent,
        bev=0.002,
    )
    # Thermostatic mixer and hand shower on the east wall
    box(
        n + "_mixer",
        x1 - 0.06,
        x1,
        hy - 0.16,
        hy + 0.16,
        1.05,
        1.13,
        M["black_metal"],
        coll_parent,
        bev=0.004,
    )
    for k, dy in enumerate((-0.11, 0.11)):
        cyl(f"{n}_knob{k}", 0, 0, 0, 0.04, 0.025, M["black_metal"], coll_parent).location = (
            x1 - 0.08,
            hy + dy,
            1.09,
        )
    tube_path(
        n + "_rail",
        [(x1 - 0.04, y0 + 0.35, 1.25), (x1 - 0.04, y0 + 0.35, 1.95)],
        0.0105,
        M["black_metal"],
        coll_parent,
    )
    hs = cyl(n + "_handshower", 0, 0, -0.11, 0.11, 0.018, M["black_metal"], coll_parent)
    hs.location = (x1 - 0.06, y0 + 0.35, 1.78)
    hs.rotation_euler.x = math.radians(18)
    cyl(n + "_handhead", 0, 0, 0, 0.02, 0.05, M["black_metal"], coll_parent).location = (
        x1 - 0.06,
        y0 + 0.31,
        1.89,
    )


def _inset_basin(name, cx, cy, top, parent, w=0.50, d=0.40, depth=0.14):
    """Classic rectangular ceramic basin dropped into a worktop: a 12 mm rim on the top, soft inner
    corners, black waste. Returns the worktop cutter."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = cx - w / 2 if v.co.x < 0 else cx + w / 2
        v.co.y = cy - d / 2 if v.co.y < 0 else cy + d / 2
        v.co.z = top - depth - 0.01 if v.co.z < 0 else top + 0.012
    lid = next(f for f in bm.faces if f.normal.z > 0.5)
    bmesh.ops.inset_region(bm, faces=[lid], thickness=0.028, depth=0)
    bmesh.ops.translate(bm, verts=lid.verts, vec=(0, 0, -depth))
    basin = mesh_obj(name + "_basin", bm, M["ceramic"], parent)
    bevel(basin, 0.008, 3)
    cyl(
        name + "_waste",
        cx,
        cy,
        top - depth + 0.012,
        top - depth + 0.016,
        0.022,
        M["black_metal"],
        parent,
    )
    return box(
        name + "_cut",
        cx - w / 2 + 0.01,
        cx + w / 2 - 0.01,
        cy - d / 2 + 0.01,
        cy + d / 2 - 0.01,
        top - 0.2,
        top + 0.1,
        None,
        parent,
    )


def bath_counter(item, root):
    """Bathroom run against one wall: a solid oak worktop over the washing machine and a floating vanity,
    a classic inset ceramic basin with a deck-mounted mixer, a mirror centred on the basin and a slim
    wall light above it. World Y params (basin_at, cabinet, light_at) are converted along the run."""
    w, d = frame_dims(item)
    p = item.get("params", {})
    n = item["id"]
    wood = M[p.get("wood", "oak_rich")]
    top = p.get("top_z", 0.90)
    tt = 0.04
    bx = world_to_local_x(item, p["basin_at"])
    worktop = box(
        n + "_top",
        0,
        w,
        -0.01,
        d,
        top - tt,
        top,
        M[p.get("top", "stone_resin")],
        root,
        bev=0.003,
        seg=3,
    )
    cy = d / 2 - 0.03
    _cut(worktop, _inset_basin(n, bx, cy, top, root))
    # Deck mixer behind the basin: round body, curved spout, lever on top
    tx, ty = bx, cy + 0.25
    cyl(n + "_tap_body", tx, ty, top, top + 0.14, 0.02, M["black_metal"], root)
    spout = [(tx, ty, top + 0.12)] + [
        (tx, ty - 0.11 * (1 - math.cos(a)), top + 0.12 + 0.03 * math.sin(a))
        for a in (math.radians(t) for t in range(15, 91, 15))
    ]
    tube_path(
        n + "_tap_spout", [*spout, (tx, ty - 0.13, top + 0.135)], 0.009, M["black_metal"], root
    )
    tube_path(
        n + "_tap_lever",
        [(tx, ty, top + 0.145), (tx, ty + 0.07, top + 0.16)],
        0.005,
        M["black_metal"],
        root,
    )
    # Floating vanity under the basin: two forest-green drawers with oak edge grips
    a, b = sorted(world_to_local_x(item, v) for v in p["cabinet"])
    z0 = p.get("cabinet_bottom", 0.42)
    box(
        n + "_carcass", a, b, 0.02, d, z0, top - 0.17, wood, root, bev=0.002
    )  # below the basin bowl
    front = M[p.get("front", "oak_rich")]
    zs = [z0, z0 + (top - tt - z0) * 0.48, top - tt]
    for i in range(2):
        box(
            f"{n}_drawer{i}",
            a + GAP,
            b - GAP,
            0.0,
            0.02,
            zs[i] + GAP,
            zs[i + 1] - GAP - 0.02,
            front,
            root,
            bev=0.0015,
        )
        box(
            f"{n}_grip{i}",
            a + GAP,
            b - GAP,
            0.0,
            0.02,
            zs[i + 1] - 0.02,
            zs[i + 1] - GAP,
            wood,
            root,
        )
    # Mirror centred on the basin, flat on the tiles, thin oak frame
    mw = p.get("mirror_width", 0.60)
    mz0, mz1 = p.get("mirror_z", (1.10, 2.05))
    box(
        n + "_mirror_frame",
        bx - mw / 2,
        bx + mw / 2,
        d - 0.022,
        d,
        mz0,
        mz1,
        wood,
        root,
        bev=0.003,
    )
    box(
        n + "_mirror",
        bx - mw / 2 + 0.015,
        bx + mw / 2 - 0.015,
        d - 0.024,
        d - 0.022,
        mz0 + 0.015,
        mz1 - 0.015,
        M["mirror"],
        root,
    )
    # Wall light on the developer's outlet above the mirror
    lx = world_to_local_x(item, p.get("light_at", p["basin_at"]))
    lz = p.get("light_z", 2.30)
    box(
        n + "_light_plate",
        lx - 0.05,
        lx + 0.05,
        d - 0.015,
        d,
        lz - 0.05,
        lz + 0.03,
        M["black_metal"],
        root,
        bev=0.003,
    )
    box(
        n + "_light_bar",
        lx - 0.25,
        lx + 0.25,
        d - 0.11,
        d - 0.015,
        lz - 0.035,
        lz - 0.005,
        M["black_metal"],
        root,
        bev=0.004,
    )
    box(
        n + "_light_diffuser",
        lx - 0.24,
        lx + 0.24,
        d - 0.10,
        d - 0.03,
        lz - 0.037,
        lz - 0.035,
        M["bulb"],
        root,
    )
    add_area_light(n + "_light", (lx, d - 0.065, lz - 0.04), (0.46, 0.06), 30, root)


def boxing(item, root):
    w, d = frame_dims(item)
    n = item["id"]
    box(n, 0, w, 0, d, 0, item["z"][1], M["bath_wall_x"], root)
    box(
        n + "_shelf",
        -0.005,
        w + 0.005,
        -0.01,
        d,
        item["z"][1],
        item["z"][1] + 0.025,
        M["oak_rich"],
        root,
        bev=0.002,
    )
    # Flush plate centred over the WC (WC centre is world X 5.72)
    cx = world_to_local_x(item, 5.72)
    box(
        n + "_flush",
        cx - 0.12,
        cx + 0.12,
        -0.006,
        0.0,
        0.95,
        1.11,
        M["black_metal"],
        root,
        bev=0.003,
    )
    box(
        n + "_flush_btn",
        cx - 0.055,
        cx + 0.055,
        -0.008,
        -0.006,
        0.98,
        1.08,
        M["black_glass"],
        root,
        bev=0.002,
    )


def wc(item, root):
    w, d = frame_dims(item)
    n = item["id"]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = (0.03 if v.co.y < 0 else 0.0) if v.co.x < 0 else (w - 0.03 if v.co.y < 0 else w)
        v.co.y = 0.0 if v.co.y < 0 else d
        v.co.z = 0.20 if v.co.z < 0 else 0.40
    bowl = mesh_obj(n + "_bowl", bm, M["ceramic"], root)
    soften(bowl, 0.09, 2)
    seat = box(n + "_seat", 0.01, w - 0.01, 0.0, d - 0.05, 0.40, 0.425, M["ceramic"], root)
    soften(seat, 0.04, 2)


def washing_machine(item, root):
    w, d = frame_dims(item)
    n = item["id"]
    box(n + "_body", 0, w, 0.0, d, 0.0, 0.85, M["plastic_white"], root, bev=0.012, seg=3)
    box(n + "_panel", 0.02, w - 0.02, -0.003, 0.0, 0.74, 0.83, M["plastic_white"], root, bev=0.002)
    box(n + "_display", w * 0.45, w * 0.70, -0.005, -0.003, 0.77, 0.81, M["black_glass"], root)
    cyl(n + "_knob", 0, 0, 0, 0.02, 0.028, M["steel"], root).matrix_basis = Matrix.Translation(
        (w * 0.82, -0.003, 0.79)
    ) @ Matrix.Rotation(math.radians(90), 4, "X")
    ring = cyl(n + "_door_ring", 0, 0, 0, 0.035, 0.20, M["steel"], root, segs=64, bev=0.006)
    ring.matrix_basis = Matrix.Translation((w / 2, 0.005, 0.42)) @ Matrix.Rotation(
        math.radians(90), 4, "X"
    )
    glass = cyl(n + "_door_glass", 0, 0, 0, 0.036, 0.155, M["black_glass"], root, segs=64)
    glass.matrix_basis = Matrix.Translation((w / 2, 0.006, 0.42)) @ Matrix.Rotation(
        math.radians(90), 4, "X"
    )


def towel_rail(item, root):
    w, d = frame_dims(item)
    n = item["id"]
    z0, z1 = item["z"]
    y = 0.0
    for i, x in enumerate((0.02, w - 0.02)):
        tube_path(f"{n}_side{i}", [(x, y, z0), (x, y, z1)], 0.012, M["black_metal"], root)
        tube_path(
            f"{n}_bracket{i}", [(x, y, z0 + 0.1), (x, d, z0 + 0.1)], 0.008, M["black_metal"], root
        )
    k = 9
    for j in range(k):
        z = z0 + 0.05 + (z1 - z0 - 0.1) * j / (k - 1)
        tube_path(f"{n}_bar{j}", [(0.02, y, z), (w - 0.02, y, z)], 0.008, M["black_metal"], root)
    t = drape(
        n + "_towel",
        0.06,
        w - 0.06,
        -0.012,
        0.012,
        z1 - 0.18,
        M["towel"],
        root,
        over_x=(0, 0),
        over_y=(0.40, 0.25),
        thickness=0.012,
        wrinkle=0.006,
        res=0.02,
    )
    t.location.z = 0


# ---------------------------------------------------------------- wall plates

PLATE_D = 0.010  # plate thickness
PLATE_W = 0.080  # one gang; a double socket is two gangs wide, double switches are two gangs tall
FACE_NORMAL = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
FACE_TILT = {
    "+y": ("x", -1),
    "-y": ("x", 1),
    "+x": ("y", 1),
    "-x": ("y", -1),
}  # rotation turning Z to the normal


def wall_plate(p, at, face, root):
    """Switch, socket, data or intercom plate flat on a wall. at is the point on the wall face, face the way
    it looks into the room, p['h'] the height of its centre. Built in world coordinates under root."""
    kind, h = p["kind"], p["h"]
    nx, ny = FACE_NORMAL[face]
    tx, ty = abs(ny), abs(nx)  # unit vector along the wall

    def slab(name, t0, t1, z0, z1, d0, d1, mat, bev=0.0):
        xs = sorted((at[0] + nx * d0 + tx * t0, at[0] + nx * d1 + tx * t1))
        ys = sorted((at[1] + ny * d0 + ty * t0, at[1] + ny * d1 + ty * t1))
        return box(name, xs[0], xs[1], ys[0], ys[1], h + z0, h + z1, mat, root, bev)

    def disc(name, t, z, r, thick, mat):
        o = cyl(name, 0, 0, -thick / 2, thick / 2, r, mat, root, segs=24)
        axis, sign = FACE_TILT[face]
        setattr(o.rotation_euler, axis, sign * math.pi / 2)
        d = PLATE_D + thick / 2
        o.location = (at[0] + nx * d + tx * t, at[1] + ny * d + ty * t, h + z)
        return o

    n = p["id"]
    if kind == "intercom":
        slab(n + "_body", -0.05, 0.05, -0.08, 0.08, 0, 0.030, M["graphite"], bev=0.004)
        slab(n + "_speaker", -0.03, 0.03, 0.035, 0.065, 0.030, 0.032, M["black_metal"])
        return
    if kind == "switch":  # double switch in a vertical frame; rockers are the two raised keys
        slab(
            n + "_plate",
            -PLATE_W / 2,
            PLATE_W / 2,
            -PLATE_W,
            PLATE_W,
            0,
            PLATE_D,
            M["pvc"],
            bev=0.002,
        )
        for i, z in enumerate((-PLATE_W / 2, PLATE_W / 2)):
            slab(
                f"{n}_key{i}",
                -0.028,
                0.028,
                z - 0.028,
                z + 0.028,
                PLATE_D,
                PLATE_D + 0.004,
                M["pvc"],
                bev=0.002,
            )
        return
    gangs = 1 if kind in ("socket", "socket400") else 2
    half = PLATE_W * gangs / 2
    slab(n + "_plate", -half, half, -PLATE_W / 2, PLATE_W / 2, 0, PLATE_D, M["pvc"], bev=0.002)
    r = 0.022 if kind == "socket400" else 0.016
    for i in range(gangs):
        disc(f"{n}_socket{i}", -half + PLATE_W * (i + 0.5), 0, r, 0.003, M["black_metal"])


GENERATORS = {
    "kitchen_run": kitchen_run,
    "tall_unit": tall_unit,
    "upper_run": upper_run,
    "open_shelves": open_shelves,
    "peninsula": peninsula,
    "counter_stool": counter_stool,
    "divider_wall": divider_wall,
    "dining_chair": dining_chair,
    "desk_chair": desk_chair,
    "sofa": sofa,
    "ottoman": ottoman,
    "rug": rug,
    "tv_console": tv_console,
    "media_wall": media_wall,
    "open_unit": open_unit,
    "bistro_table": bistro_table,
    "bistro_chair": bistro_chair,
    "tv": tv,
    "floor_lamp": floor_lamp,
    "wardrobe": wardrobe,
    "floating_shelf": floating_shelf,
    "mirror": mirror,
    "bed": bed,
    "standing_desk": standing_desk,
    "walkin_shower": walkin_shower,
    "bath_counter": bath_counter,
    "wall_cabinet": wall_cabinet,
    "l_wardrobe": l_wardrobe,
    "partition": partition,
    "slat_screen": slat_screen,
    "office_chair": office_chair,
    "art_print": art_print,
    "boxing": boxing,
    "wc": wc,
    "washing_machine": washing_machine,
    "towel_rail": towel_rail,
}
WORLD_SPACE = {"walkin_shower", "l_wardrobe"}  # generators that build directly in world coordinates
