"""Place furniture placeholder blocks from data/furniture.json into the shell and render the layout plan.

    blender --background --factory-startup --python scripts/build_layout.py

Reads blender/apartment_shell.blend (run build_shell.py first). Writes renders/layout_proposal.png and
blender/apartment_layout.blend. The placeholders are swapped for real furniture in the interior step.
"""

import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_shell as shell  # noqa: E402

ROOT = shell.ROOT
FURN = json.loads((ROOT / "data" / "furniture.json").read_text())

CAT_COLORS = {
    "kitchen": (0.55, 0.42, 0.30, 1),
    "kitchen_upper": (0.75, 0.62, 0.48, 1),
    "table": (0.35, 0.22, 0.12, 1),
    "seat": (0.20, 0.35, 0.55, 1),
    "rug": (0.80, 0.74, 0.62, 1),
    "storage": (0.45, 0.30, 0.18, 1),
    "tv": (0.02, 0.02, 0.02, 1),
    "bed": (0.30, 0.45, 0.35, 1),
    "bath": (0.92, 0.92, 0.95, 1),
    "boxing": (0.60, 0.60, 0.60, 1),
    "decor": (0.35, 0.55, 0.30, 1),
    "wall": (0.18, 0.18, 0.18, 1),
}


def main():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / "blender" / "apartment_shell.blend"))
    c_furn = shell.collection("Furniture")
    m_text = bpy.data.materials["Annotation"]
    rooms = {}
    for it in FURN["items"]:
        room = rooms.get(it["room"]) or shell.collection("Furniture_" + it["room"], c_furn)
        rooms[it["room"]] = room
        x0, x1, y0, y1 = it["footprint"]
        z0, z1 = it["z"]
        z0 = max(z0, 0.005)  # keep the base off the floor plane so the cut plan doesn't z-fight
        obj = shell.box(it["id"], x0, x1, y0, y1, z0, z1, room)
        obj["placeholder"] = True
        obj["cat"] = it["cat"]
        if it.get("label"):
            lab = shell.label(
                it["label"],
                (x0 + x1) / 2,
                (y0 + y1) / 2,
                shell.LABEL_Z,
                bpy.data.collections["Annotations"],
                m_text,
            )
            lab.data.size = 0.11
            lab.name = "Label_furn_" + it["id"]

    # Room labels would collide with furniture; nudge the big ones into free floor
    for name, (x, y) in {
        "Label_Living room + kitchen + hall": (3.27, 2.30),
        "Label_Bedroom": (5.70, 4.08),
        "Label_Bathroom": (5.85, 1.45),
    }.items():
        if name in bpy.data.objects:
            obj = bpy.data.objects[name]
            obj.location.x, obj.location.y = x, y
            obj.data.size = 0.13

    shell.render_plan(
        ROOT / "renders" / "layout_proposal.png",
        extra_colors={"Furniture": lambda o: CAT_COLORS[o["cat"]]},
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "blender" / "apartment_layout.blend"))
    report_clearances()


def report_clearances():
    """Print the clearances that drive the layout, so changes to furniture.json can be checked quickly."""
    f = {it["id"]: it["footprint"] for it in FURN["items"]}
    checks = [
        ("U aisle: south counter/fridge -> peninsula", f["peninsula"][2] - f["fridge"][3], 0.90),
        ("Entry walkway: counter end -> partition", 4.054 - f["peninsula"][1], 0.90),
        ("Entrance door swing (to Y 1.05) -> counter", f["peninsula"][2] - 1.05, 0.0),
        ("North chairs -> footrest (walkway)", f["footrest"][2] - f["dining_chair_n1"][3], 0.90),
        ("North chairs -> sideboard (walkway)", f["dining_chair_n1"][0] - f["sideboard"][1], 0.90),
        ("Sideboard -> sofa end", f["sofa"][2] - f["sideboard"][3], 0.05),
        (
            "South chairs -> hob run front (pull-out room)",
            f["dining_chair_s1"][2] - f["kitchen_base_south"][3],
            0.60,
        ),
        ("Entry walkway: south chairs -> partition", 4.054 - f["dining_chair_s2"][1], 0.90),
        ("North chairs -> sofa end (walkway)", f["sofa"][2] - f["dining_chair_n1"][3], 0.60),
        (
            "Sink run length (fits a 60 cm sink unit)",
            f["kitchen_base_west"][3] - f["kitchen_base_west"][2],
            0.60,
        ),
        ("Fridge front -> peninsula (U aisle)", f["peninsula"][2] - f["fridge"][3], 0.90),
        ("South run end -> entrance opening (X 2.904)", 2.904 - f["kitchen_base_south"][1], 0.0),
        (
            "Footrest -> balcony leaf hinge (radius 0.84)",
            ((f["footrest"][1] - 1.40) ** 2 + (6.29 - f["footrest"][3]) ** 2) ** 0.5 - 0.84,
            0.0,
        ),
        ("Sofa -> TV viewing distance", f["tv"][0] - (f["sofa"][0] + f["sofa"][1]) / 2, 2.5),
        ("Bed foot -> bedroom west wall", f["bed"][0] - 4.153, 0.70),
        ("Wardrobe (sliding) front -> bed side", f["bed"][2] - f["bed_wardrobe"][3], 0.70),
        ("Desk -> balcony door swing (X 4.93)", f["desk"][0] - 4.93, 0.0),
        ("Desk back -> bedroom radiator front (Y 7.69)", 7.69 - f["desk"][3], -0.01),
        ("Sofa arm -> curtain plane (Y 6.04)", 6.04 - f["sofa"][3], 0.03),
        ("Bed -> desk (chair zone)", f["desk"][2] - f["bed"][3], 0.90),
        ("Shower entry width (glass from X)", 6.00 - f["shower"][0], 0.60),
        (
            "Slat screen end -> peninsula (way into the U)",
            f["peninsula"][2] - f["slat_screen"][3],
            0.90,
        ),
        (
            "Slat screen -> south run end (butts, no gap)",
            f["slat_screen"][0] - f["kitchen_base_south"][1],
            0.0,
        ),
        (
            "Open entrance leaf (X 3.956) -> L-wardrobe return",
            f["hall_wardrobe"][1] - 0.40 - 3.956,
            0.60,
        ),
        ("L-wardrobe return -> bathroom door lining (Y 1.04)", 1.04 - f["hall_wardrobe"][3], 0.0),
        ("Bedroom plant out of the bed-foot passage (X)", 6.76 - 0.20 - f["desk_chair"][1], 0.0),
        ("Basin counter -> WC front (bathroom aisle)", f["bath_counter"][0] - f["wc"][1], 0.45),
    ]
    print("\n=== Layout clearances ===")
    for name, v, need in checks:
        print(f"  {'OK ' if v >= need else 'LOW'} {name:48s} {v:5.2f} m  (min {need:.2f})")


if __name__ == "__main__":
    main()
