import ci_matrix
from conftest import load


def test_matrix_covers_day_evening_and_plan():
    cfg = load("cameras")
    jobs = ci_matrix.jobs(cfg)
    names = [j["name"] for j in jobs]
    assert len(names) == len(set(names))
    cams = [c for c in cfg["cameras"] if c != "walk"]
    assert [j["cams"] for j in jobs if j["mode"] == "day" and not j["plan"]] == cams
    assert "walk" not in {j["cams"] for j in jobs}
    assert sum(j["plan"] for j in jobs) == 1


def test_evening_skips_the_listed_views():
    cfg = load("cameras")
    evening = ci_matrix.evening_cams(cfg)
    assert not set(cfg["evening_skip"]) & set(evening)
    assert "bathroom_shower" in cfg["cameras"] and "kitchen_island" in evening


def test_view_names_have_no_plan():
    names = ci_matrix.view_names(load("cameras"))
    assert "plan" not in names and "living_hero" in names and "bathroom_vanity_evening" in names
