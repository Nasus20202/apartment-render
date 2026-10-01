"""Build the architectural shell of the apartment from data/floorplan.json.

Run headless:
    blender --background --factory-startup --python scripts/build_shell.py

Outputs:
    blender/apartment_shell.blend
    renders/shell_topdown.png        orthographic plan (ceiling hidden)
    renders/shell_topdown_map.json   pixel <-> metre mapping, used by verify_overlay.py
    renders/shell_overview_{sw,nw}.png  perspective overviews of the shell
"""

import json
import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "floorplan.json").read_text())

MM_PER_PT = DATA["scale"]["mm_per_pt"]
OX, OY = DATA["origin_pt"]["x"], DATA["origin_pt"]["y"]
H = {k: v["value"] for k, v in DATA["heights_m"].items()}
CEIL = H["ceiling"]
PLAN_PX_PER_M = 200
PLAN_CUT_Z = 1.2  # section height of the floor-plan render (standard plan convention)
LABEL_Z = 1.15  # just below the cut so labels stay visible in plan

# Flat fill colours for the floor-plan render (Workbench object colour)
PLAN_COLORS = {
    "Walls": (0.18, 0.18, 0.18, 1),
    "Floors": (0.93, 0.90, 0.84, 1),
    "Openings": (0.05, 0.16, 0.30, 1),
    "Exterior": (0.82, 0.82, 0.82, 1),
    "Annotations": (0.1, 0.1, 0.1, 1),
    "Architecture": (0.6, 0.6, 0.6, 1),
}
FLOOR_PLAN_COLORS = {"Floor_bathroom": (0.85, 0.89, 0.92, 1)}


def X(px):
    return (px - OX) * MM_PER_PT / 1000.0


def Y(py):
    return (OY - py) * MM_PER_PT / 1000.0


def rect_m(r):
    """Plan rect [x0, x1, y0, y1] in pt -> (xmin, xmax, ymin, ymax) in metres."""
    xs, ys = sorted((X(r[0]), X(r[1]))), sorted((Y(r[2]), Y(r[3])))
    return xs[0], xs[1], ys[0], ys[1]


# ---------------------------------------------------------------- scene setup


def reset_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0
    s.unit_settings.length_unit = "METERS"


def collection(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def material(name, rgb, roughness=0.6, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, alpha)  # used by Workbench
    bsdf = m.node_tree.nodes["Principled BSDF"] if m.node_tree else None
    if bsdf is None:
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if transmission:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    return m


def box(name, xmin, xmax, ymin, ymax, zmin, zmax, coll, mat=None):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = xmin if v.co.x < 0 else xmax
        v.co.y = ymin if v.co.y < 0 else ymax
        v.co.z = zmin if v.co.z < 0 else zmax
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def prism(name, poly_xy, zmin, zmax, coll, mat=None):
    """Extrude a 2D polygon (metres, CCW or CW) between zmin and zmax."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, zmin)) for x, y in poly_xy]
    face = bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=[face])
    if face.normal.z > 0:
        face.normal_flip()
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, zmax - zmin))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def apply_cut(target, cutter):
    mod = target.modifiers.new("cut_" + cutter.name, "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    bpy.context.view_layer.objects.active = target
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def polygon_area(poly):
    a = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


# ---------------------------------------------------------------- build


def build():
    reset_scene()

    c_arch = collection("Architecture")
    c_walls = collection("Walls", c_arch)
    c_floors = collection("Floors", c_arch)
    c_ceil = collection("Ceilings", c_arch)
    c_open = collection("Openings", c_arch)
    c_ext = collection("Exterior")
    c_ann = collection("Annotations")
    c_cam = collection("Cameras_Lights")
    c_tmp = collection("_cutters")

    m_wall = material("Wall_Plaster", (0.86, 0.85, 0.82))
    m_wall_ext = material("Wall_Exterior", (0.78, 0.77, 0.74))
    m_shaft = material("Shaft", (0.70, 0.70, 0.70))
    m_ceil = material("Ceiling", (0.95, 0.95, 0.95))
    m_frame = material("Frame_PVC", (0.95, 0.95, 0.95), roughness=0.4)
    m_glass = material("Glass", (0.75, 0.85, 0.9), roughness=0.0, alpha=0.3, transmission=1.0)
    m_door = material("Door_Leaf", (0.92, 0.90, 0.86), roughness=0.5)
    m_text = material("Annotation", (0.05, 0.05, 0.05))
    m_balc = material("Balcony_Concrete", (0.6, 0.6, 0.58))
    floor_mats = {
        "living_kitchen": material("Floor_Living", (0.72, 0.60, 0.45)),
        "bedroom": material("Floor_Bedroom", (0.68, 0.56, 0.42)),
        "bathroom": material("Floor_Bathroom", (0.80, 0.80, 0.78)),
    }
    wall_mat = {
        "party": m_wall,
        "exterior": m_wall_ext,
        "corridor": m_wall,
        "partition": m_wall,
        "shaft": m_shaft,
    }

    # Walls
    walls = {}
    for w in DATA["walls"]:
        xmin, xmax, ymin, ymax = rect_m(w["rect_pt"])
        walls[w["id"]] = box(
            w["id"], xmin, xmax, ymin, ymax, 0.0, CEIL, c_walls, wall_mat[w["type"]]
        )
        walls[w["id"]]["plan_type"] = w["type"]

    # Openings: cut the host wall, then add frames, glass and leaves
    for o in DATA["openings"]:
        wall = walls[o["wall"]]
        wxmin, wxmax, wymin, wymax = rect_m(
            next(w for w in DATA["walls"] if w["id"] == o["wall"])["rect_pt"]
        )
        sill = H[o["sill"]] if "sill" in o else o.get("sill_m", 0.0)
        head = H[o["head"]]
        a, b = (
            sorted((X(o["span_pt"][0]), X(o["span_pt"][1])))
            if o["axis"] == "x"
            else sorted((Y(o["span_pt"][0]), Y(o["span_pt"][1])))
        )
        eps = 0.02
        if o["axis"] == "x":
            cut = box("cut_" + o["id"], a, b, wymin - eps, wymax + eps, sill, head, c_tmp)
        else:
            cut = box("cut_" + o["id"], wxmin - eps, wxmax + eps, a, b, sill, head, c_tmp)
        apply_cut(wall, cut)
        add_opening_elements(
            o, a, b, (wxmin, wxmax, wymin, wymax), sill, head, c_open, m_frame, m_glass, m_door
        )

    for obj in list(c_tmp.objects):
        bpy.data.objects.remove(obj)
    bpy.data.collections.remove(c_tmp)

    # Floors, ceilings, labels
    report = []
    for r in DATA["rooms"]:
        poly = [(X(px), Y(py)) for px, py in r["polygon_pt"]]
        prism("Floor_" + r["id"], poly, -0.02, 0.0, c_floors, floor_mats[r["id"]])
        prism("Ceiling_" + r["id"], poly, CEIL, CEIL + 0.02, c_ceil, m_ceil)
        area = polygon_area(poly)
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        report.append((r["name"], area, max(xs) - min(xs), max(ys) - min(ys)))
        cx, cy = room_label_point(r["id"], poly)
        label(f"{r['name']}\n{area:.2f} m²", cx, cy, LABEL_Z, c_ann, m_text)

    # Balcony
    b = DATA["balcony"]
    bz = H["balcony_floor_offset"]
    xmin, xmax, ymin, ymax = rect_m(b["slab_pt"])
    box("Balcony_Slab", xmin, xmax, ymin, ymax, bz - 0.18, bz, c_ext, m_balc)
    xmin, xmax, ymin, ymax = rect_m(b["railing_pt"])
    box("Balcony_Railing", xmin, xmax, ymin, ymax, bz, bz + H["balcony_railing"], c_ext, m_glass)
    xmin, xmax, ymin, ymax = rect_m(b["privacy_screen_pt"])
    box("Balcony_PrivacyScreen", xmin, xmax, ymin, ymax, bz, bz + 2.0, c_ext, m_wall_ext)

    # Structural slab under everything, so the shell doesn't float
    xs = [v for w in DATA["walls"] for v in rect_m(w["rect_pt"])[:2]]
    ys = [v for w in DATA["walls"] for v in rect_m(w["rect_pt"])[2:]]
    box("Structural_Slab", min(xs), max(xs), min(ys), max(ys), -0.22, -0.02, c_arch, m_shaft)

    bounds = (min(xs), max(xs), min(ys), max(ys))
    setup_cameras_and_light(c_cam, bounds)

    print("\n=== Room summary (from plan scale) ===")
    total = 0.0
    for name, area, w, d in report:
        total += area
        print(f"  {name:32s} {area:6.2f} m²   bbox {w:.2f} x {d:.2f} m")
    print(f"  {'TOTAL usable floor':32s} {total:6.2f} m²\n")
    return c_ceil, c_ann, bounds


def room_label_point(room_id, poly):
    # Simple per-room placement in clear floor area, avoiding the L-shapes' notches
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    if room_id == "living_kitchen":
        return X(470), Y(430)
    if room_id == "bathroom":
        return X(702), Y(580)
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def label(text, x, y, z, coll, mat):
    cu = bpy.data.curves.new("Label", "FONT")
    cu.body = text
    cu.size = 0.22
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    obj = bpy.data.objects.new("Label_" + text.split("\n")[0], cu)
    obj.location = (x, y, z)
    obj.data.materials.append(mat)
    coll.objects.link(obj)
    return obj


def add_opening_elements(o, a, b, wb, sill, head, coll, m_frame, m_glass, m_door):
    """Simple PVC frames, glazing and leaves. The leaves are opened 90 degrees so the plan shows the swing."""
    wxmin, wxmax, wymin, wymax = wb
    along_x = o["axis"] == "x"
    # Frames sit at the middle of the wall thickness
    mid = (wymin + wymax) / 2 if along_x else (wxmin + wxmax) / 2
    fd, fw = 0.07, 0.06  # frame depth, frame profile width

    def frame_box(name, s0, s1, z0, z1, depth, mat):
        if along_x:
            return box(name, s0, s1, mid - depth / 2, mid + depth / 2, z0, z1, coll, mat)
        return box(name, mid - depth / 2, mid + depth / 2, s0, s1, z0, z1, coll, mat)

    oid = o["id"]
    # Outer frame: two jambs and a head; a bottom rail on windows
    # Parts butt against each other rather than overlap: coplanar overlapping faces render as black
    # patches in Cycles. The head and sill rail run full width; the jambs fit between them.
    jamb_z0 = sill + fw if o["kind"] == "window" else sill
    frame_box(oid + "_jamb_a", a, a + fw, jamb_z0, head - fw, fd, m_frame)
    frame_box(oid + "_jamb_b", b - fw, b, jamb_z0, head - fw, fd, m_frame)
    frame_box(oid + "_head", a, b, head - fw, head, fd, m_frame)
    if o["kind"] == "window":
        frame_box(oid + "_sillrail", a, b, sill, sill + fw, fd, m_frame)
        frame_box(oid + "_glass", a + fw, b - fw, sill + fw, head - fw, 0.02, m_glass)
        return

    parts = o.get("parts_pt") or [{"kind": "door", "span": o["span_pt"]}]
    for i, p in enumerate(parts):
        s0, s1 = (
            sorted((X(p["span"][0]), X(p["span"][1])))
            if along_x
            else sorted((Y(p["span"][0]), Y(p["span"][1])))
        )
        s0, s1 = max(s0, a + fw), min(s1, b - fw)
        if p["kind"] == "fixed":
            frame_box(f"{oid}_fixed{i}_glass", s0, s1, sill + fw, head - fw, 0.02, m_glass)
            frame_box(f"{oid}_mullion{i}", s1 - fw / 2, s1 + fw / 2, sill, head - fw, fd, m_frame)
            continue
        glazed = o["kind"] == "window_door" or oid == "O_bedroom_balcony"
        if p["kind"] == "door_pair":
            half = (s1 - s0) / 2
            leaf(
                f"{oid}_leafL",
                s0,
                half,
                +1,
                o,
                mid,
                sill,
                head - fw,
                glazed,
                coll,
                m_frame,
                m_glass,
                m_door,
            )
            leaf(
                f"{oid}_leafR",
                s1,
                half,
                -1,
                o,
                mid,
                sill,
                head - fw,
                glazed,
                coll,
                m_frame,
                m_glass,
                m_door,
            )
        else:
            hinge_at_start = o["hinge"] in ("west", "south")
            start = s0 if hinge_at_start else s1
            leaf(
                f"{oid}_leaf",
                start,
                s1 - s0,
                +1 if hinge_at_start else -1,
                o,
                mid,
                sill,
                head - fw,
                glazed,
                coll,
                m_frame,
                m_glass,
                m_door,
            )


def leaf(name, hinge_s, width, direction, o, mid, z0, z1, glazed, coll, m_frame, m_glass, m_door):
    """Door leaf opened 90 degrees into swing_dir; hinge at hinge_s along the opening axis."""
    t = 0.04
    dx, dy = o["swing_dir"]
    along_x = o["axis"] == "x"
    hs = hinge_s + direction * t / 2  # keep the leaf inside the opening
    if along_x:
        x0, x1 = sorted((hs - t / 2, hs + t / 2))
        y0, y1 = sorted((mid, mid + dy * width))
    else:
        y0, y1 = sorted((hs - t / 2, hs + t / 2))
        x0, x1 = sorted((mid, mid + dx * width))
    obj = box(name, x0, x1, y0, y1, z0, z1, coll, m_glass if glazed else m_door)
    obj["swing_dir"] = list(o["swing_dir"])
    # Swing arc on the floor, from the leaf's open position back to the closed position
    if along_x:
        hinge, closed, opened = Vector((hs, mid)), Vector((direction, 0)), Vector((0, dy))
    else:
        hinge, closed, opened = Vector((mid, hs)), Vector((0, direction)), Vector((dx, 0))
    pts = [
        hinge + width * (math.cos(t) * closed + math.sin(t) * opened)
        for t in (math.radians(a) for a in range(0, 91, 5))
    ]
    swing_arc(name + "_swing", pts)
    return obj


def swing_arc(name, pts):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.006
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, v in zip(sp.points, pts):
        p.co = (v.x, v.y, 0.01, 1.0)
    obj = bpy.data.objects.new(name, cu)
    bpy.data.collections["Annotations"].objects.link(obj)


# ---------------------------------------------------------------- cameras, light, render


def setup_cameras_and_light(coll, bounds):
    xmin, xmax, ymin, ymax = bounds
    margin = 0.6
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    w, h = xmax - xmin + 2 * margin, ymax - ymin + 2 * margin

    cam = bpy.data.cameras.new("Cam_TopDown")
    cam.type = "ORTHO"
    cam.ortho_scale = max(w, h)
    cam.clip_start = 20.0 - PLAN_CUT_Z  # section cut: everything above PLAN_CUT_Z is clipped
    cam.clip_end = 100
    top = bpy.data.objects.new("Cam_TopDown", cam)
    top.location = (cx, cy, 20.0)
    coll.objects.link(top)
    top["plan_frame_m"] = [cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2]

    for name, loc in (
        ("Cam_Overview_SW", (cx - 7.0, cy - 8.0, 10.0)),
        ("Cam_Overview_NW", (cx - 8.0, cy + 7.5, 9.0)),
    ):
        cam2 = bpy.data.cameras.new(name)
        cam2.lens = 28
        ov = bpy.data.objects.new(name, cam2)
        ov.location = loc
        look_at(ov, Vector((cx, cy, 0.3)))
        coll.objects.link(ov)

    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    sun.angle = math.radians(2)
    s = bpy.data.objects.new("Sun", sun)
    s.rotation_euler = (math.radians(50), 0, math.radians(30))
    coll.objects.link(s)


def look_at(obj, target):
    d = target - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render_plan(filepath, extra_colors=None):
    """Orthographic section-cut plan render in flat Workbench colours.

    extra_colors maps collection name -> RGBA (or a callable obj -> RGBA) for collections
    outside PLAN_COLORS, e.g. furniture. Writes a pixel/metre mapping JSON next to the PNG.
    """
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "FLAT"
    sh.color_type = "OBJECT"
    sh.show_shadows = False
    sh.show_cavity = False
    colors = dict(PLAN_COLORS, **(extra_colors or {}))
    for coll_name, col in colors.items():
        coll = bpy.data.collections.get(coll_name)
        if coll is None:
            continue
        for obj in coll.all_objects if callable(col) else coll.objects:
            obj.color = col(obj) if callable(col) else FLOOR_PLAN_COLORS.get(obj.name, col)
    sh.show_object_outline = True
    sh.object_outline_color = (0.0, 0.0, 0.0)
    scene.display.render_aa = "8"
    scene.render.film_transparent = False
    sh.background_type = "VIEWPORT"
    sh.background_color = (1, 1, 1)
    scene.view_settings.view_transform = "Standard"

    top = bpy.data.objects["Cam_TopDown"]
    fx0, fx1, fy0, fy1 = top["plan_frame_m"]
    scene.camera = top
    scene.render.resolution_x = round((fx1 - fx0) * PLAN_PX_PER_M)
    scene.render.resolution_y = round((fy1 - fy0) * PLAN_PX_PER_M)
    scene.render.resolution_percentage = 100
    hidden = {c: c.hide_render for c in bpy.data.collections}
    bpy.data.collections["Ceilings"].hide_render = True
    bpy.data.collections["Annotations"].hide_render = False
    scene.render.filepath = str(filepath)
    bpy.ops.render.render(write_still=True)
    for c, h in hidden.items():
        c.hide_render = h
    Path(filepath).with_name(Path(filepath).stem + "_map.json").write_text(
        json.dumps(
            {
                "px_per_m": PLAN_PX_PER_M,
                "frame_m": [fx0, fx1, fy0, fy1],
                "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            },
            indent=2,
        )
    )


def render_views(c_ceil, c_ann, bounds):
    scene = bpy.context.scene
    renders = ROOT / "renders"
    renders.mkdir(exist_ok=True)
    render_plan(renders / "shell_topdown.png")
    sh = scene.display.shading
    top = bpy.data.objects["Cam_TopDown"]

    # --- Overview: studio lighting, ceilings hidden
    sh.light = "STUDIO"
    sh.show_shadows = True
    sh.show_cavity = True
    sh.cavity_type = "WORLD"
    sh.color_type = "MATERIAL"
    c_ann.hide_render = True
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1440
    for cam_name, suffix in (("Cam_Overview_SW", "sw"), ("Cam_Overview_NW", "nw")):
        scene.camera = bpy.data.objects[cam_name]
        scene.render.filepath = str(renders / f"shell_overview_{suffix}.png")
        bpy.ops.render.render(write_still=True)

    # Restore the defaults saved in the .blend
    c_ceil.hide_render = False
    c_ann.hide_render = False
    scene.camera = top


if __name__ == "__main__":
    c_ceil, c_ann, bounds = build()
    render_views(c_ceil, c_ann, bounds)
    out = ROOT / "blender" / "apartment_shell.blend"
    out.parent.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("Saved", out)
