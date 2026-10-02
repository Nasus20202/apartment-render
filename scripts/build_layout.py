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
from clearances import report_clearances  # noqa: E402

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
    report_clearances(FURN["items"])


if __name__ == "__main__":
    main()
