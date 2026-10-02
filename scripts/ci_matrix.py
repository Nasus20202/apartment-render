"""List the final render jobs for the GitHub Actions matrix (pure Python, no Blender).

python3 scripts/ci_matrix.py            # JSON for `matrix: ${{ fromJSON(...) }}`
python3 scripts/ci_matrix.py --evening  # evening camera names, space separated (Makefile)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def jobs(cfg):
    """Every day view, the evening views not in `evening_skip`, and the furnished plan."""
    cams = [c for c in cfg["cameras"] if c != "walk"]
    skip = set(cfg.get("evening_skip", []))
    out = [{"name": c, "mode": "day", "cams": c, "plan": False, "file": f"{c}.png"} for c in cams]
    out += [
        {
            "name": f"{c}_evening",
            "mode": "evening",
            "cams": c,
            "plan": False,
            "file": f"{c}_evening.png",
        }
        for c in cams
        if c not in skip
    ]
    out.append(
        {"name": "plan", "mode": "day", "cams": "none", "plan": True, "file": "plan_furnished.png"}
    )
    return out


def evening_cams(cfg):
    return [j["cams"] for j in jobs(cfg) if j["mode"] == "evening"]


if __name__ == "__main__":
    cfg = json.loads((ROOT / "data" / "cameras.json").read_text())
    if "--evening" in sys.argv:
        print(" ".join(evening_cams(cfg)))
    else:
        print(json.dumps({"include": jobs(cfg)}))
