"""Render interior views from blender/apartment.blend.

    blender -b blender/apartment.blend -P scripts/render.py -- [--cams a,b] [--samples N] [--noise T]
                                                              [--scale PCT] [--mode day|evening] [--out DIR] [--plan]

Defaults: every camera in data/cameras.json except 'walk', 512 samples (adaptive, noise threshold 0.005), 100 %, day, renders/interior/.
--cams none renders no camera views (use with --plan). A camera's optional "exposure" overrides the scene's.
--plan also renders the furnished section-cut plan (Cycles, top camera). Uses the GPU (HIP/CUDA/OptiX/oneAPI)
when Blender finds one, otherwise the CPU.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def pick_device():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            bpy.context.scene.cycles.device = "GPU"
            return f"{kind}: " + ", ".join(d.name for d in gpus)
    bpy.context.scene.cycles.device = "CPU"
    return "CPU"


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--cams", default="")
    ap.add_argument("--samples", type=int, default=512)
    ap.add_argument("--noise", type=float, default=0.005, help="adaptive sampling noise threshold")
    ap.add_argument("--scale", type=int, default=100)
    ap.add_argument("--mode", default="day", choices=("day", "evening"))
    ap.add_argument("--out", default=str(ROOT / "renders" / "interior"))
    ap.add_argument("--plan", action="store_true")
    a = ap.parse_args(argv)

    scene = bpy.context.scene
    print("Device:", pick_device())
    scene.cycles.samples = a.samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = a.noise
    scene.render.resolution_percentage = a.scale
    modes.set_mode(a.mode)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    cam_cfg = json.loads((ROOT / "data" / "cameras.json").read_text())["cameras"]
    all_cams = [c for c in cam_cfg if c != "walk"]
    cams = [] if a.cams == "none" else [c for c in a.cams.split(",") if c] or all_cams
    base_exposure = scene.view_settings.exposure
    suffix = "" if a.mode == "day" else "_evening"
    for name in cams:
        scene.camera = bpy.data.objects["Cam_" + name]
        modes.set_mode(a.mode, lamps=True if cam_cfg[name].get("lamps") else None)
        scene.view_settings.exposure = cam_cfg[name].get("exposure", base_exposure)
        scene.render.filepath = str(out / f"{name}{suffix}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {name} in {time.time() - t:.0f}s -> {scene.render.filepath}")

    if a.plan:
        top = bpy.data.objects["Cam_TopDown"]
        scene.camera = top
        scene.view_settings.exposure = base_exposure - 2.4
        fx0, fx1, fy0, fy1 = top["plan_frame_m"]
        scene.render.resolution_x = round((fx1 - fx0) * 200)
        scene.render.resolution_y = round((fy1 - fy0) * 200)
        # The camera clip hides everything above the cut, but ceilings, the roof seal and the neighbouring
        # buildings would still block the sun and sky, so take them and the ceiling fixtures out of the render.
        bpy.data.collections["Ceilings"].hide_render = True
        bpy.data.objects["Roof_Seal"].hide_render = True
        for o in bpy.data.objects:
            if o.name.startswith("Building_"):
                o.hide_render = True
        for o in bpy.data.collections["Lighting"].objects:
            o.hide_render = o.type != "LIGHT"
        # Overhead, soft light for the plan so tall walls don't throw hard shadows across the rooms
        sun = bpy.data.objects.get("Sun")
        if sun:
            sun.rotation_euler = (0.12, 0.08, 0.6)
            sun.data.angle = math.radians(12)
            sun.data.energy *= 0.6
        scene.render.filepath = str(out / f"plan_furnished{suffix}.png")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"Rendered plan in {time.time() - t:.0f}s -> {scene.render.filepath}")


if __name__ == "__main__":
    main()
