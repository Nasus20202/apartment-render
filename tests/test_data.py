"""Schema and consistency checks for data/*.json, the single source of truth for the build."""

import ast

import pytest
from conftest import ROOT, load

DATA_FILES = sorted(p.stem for p in (ROOT / "data").glob("*.json"))
FACINGS = {"+x", "-x", "+y", "-y"}


@pytest.mark.parametrize("name", DATA_FILES)
def test_json_parses(name):
    assert load(name)


def test_scale_matches_pt_per_m(floorplan):
    s = floorplan["scale"]
    assert s["pt_per_m"] == pytest.approx(56.68)
    assert s["mm_per_pt"] == pytest.approx(1000 / s["pt_per_m"], rel=1e-4)


def test_ceiling_height_is_confirmed(floorplan):
    assert floorplan["heights_m"]["ceiling"]["value"] == 2.95
    assert not floorplan["heights_m"]["ceiling"]["assumed"]


def test_assumed_heights_have_notes(floorplan):
    for name, h in floorplan["heights_m"].items():
        assert "value" in h and "assumed" in h, name
        if h["assumed"]:
            assert h["note"], f"{name} is assumed but has no note"


def test_openings_reference_known_walls_and_heights(floorplan):
    walls = {w["id"] for w in floorplan["walls"]}
    assert len(walls) == len(floorplan["walls"]), "duplicate wall ids"
    for o in floorplan["openings"]:
        assert o["wall"] in walls, o["id"]
        assert o["head"] in floorplan["heights_m"], o["id"]


def test_furniture_ids_unique(items):
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))


def test_furniture_items_well_formed(items, floorplan):
    for it in items:
        x0, x1, y0, y1 = it["footprint"]
        z0, z1 = it["z"]
        assert x0 < x1 and y0 < y1, f"{it['id']}: inverted footprint"
        assert 0 <= z0 < z1 <= floorplan["heights_m"]["ceiling"]["value"], f"{it['id']}: bad z"
        assert it["facing"] in FACINGS, it["id"]
        assert it["room"] and it["cat"] and it["source"], it["id"]


def test_furniture_categories_have_layout_colours(items):
    """build_layout.CAT_COLORS is indexed by cat; a new category must get a colour."""
    import re

    src = (ROOT / "scripts" / "build_layout.py").read_text()
    colours = set(re.findall(r'^    "(\w+)": \(', src, re.M))
    assert {i["cat"] for i in items} <= colours


def generator_names():
    """Keys of furniture.GENERATORS, read with ast because the module needs bpy."""
    tree = ast.parse((ROOT / "scripts" / "furniture.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "GENERATORS":
            return {k.value for k in node.value.keys}
    raise AssertionError("GENERATORS not found")


def test_furniture_sources_are_known(items):
    gens = generator_names()
    models = load("assets")["polyhaven_models"]
    for it in items:
        kind, _, ref = it["source"].partition(":")
        if kind == "proc":
            assert ref in gens, f"{it['id']}: no generator {ref}"
        elif kind == "polyhaven":
            assert ref in models, f"{it['id']}: {ref} missing from data/assets.json"
        else:
            pytest.fail(f"{it['id']}: unknown source kind {kind}")


def test_lighting_outlets_exist(lighting, floorplan):
    outlets = floorplan["fixtures_reference"]["light_outlets"]
    for f in lighting["fixtures"]:
        for o in f.get("outlets", [f["outlet"]] if "outlet" in f else []):
            assert o in outlets, f"{f['id']} hangs on unknown outlet {o}"


def test_lighting_fixture_ids_unique(lighting):
    ids = [f["id"] for f in lighting["fixtures"]]
    assert len(ids) == len(set(ids))


def test_off_outlet_fixtures_are_noted(lighting):
    """Rule 3: a fixture that is not on an outlet must say so."""
    for f in lighting["fixtures"]:
        if not (f.get("outlets") or f.get("outlet")):
            assert f.get("note"), f"{f['id']} is off the installation plan without a note"


def test_electrical_points(electrical):
    pts = electrical["points"]
    ids = [p["id"] for p in pts]
    assert len(ids) == len(set(ids))
    for p in pts:
        assert p["face"] in FACINGS, p["id"]
        if p.get("h_assumed"):
            assert p.get("note") or p.get("source"), p["id"]


def test_electrical_model_overrides(electrical):
    """A point set off its plan position in the model must say why."""
    for p in electrical["points"]:
        m = p.get("model")
        if m:
            assert len(m["at"]) == 2, p["id"]
            assert p.get("note"), f"{p['id']} is moved off the plan without a note"


def test_cameras(floorplan):
    cams = load("cameras")["cameras"]
    for name, c in cams.items():
        assert len(c["loc"]) == 3 and len(c["target"]) == 3, name
        assert c["lens"] > 0, name
        assert c["loc"] != c["target"], name


def test_assets_manifest():
    m = load("assets")
    for kind in ("polyhaven_models", "polyhaven_hdris", "ambientcg"):
        for key, v in m[kind].items():
            assert v["res"], f"{kind}/{key}"
    for key, v in m.get("images", {}).items():
        assert v["commons"].startswith("File:"), key
