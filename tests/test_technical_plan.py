"""Pure geometry helpers of the technical plan (matplotlib on the Agg backend, no display needed)."""

import pytest
import technical_plan as tp


def test_origin_maps_to_zero(floorplan):
    o = floorplan["origin_pt"]
    assert tp.mx(o["x"]) == pytest.approx(0)
    assert tp.my(o["y"]) == pytest.approx(0)


def test_axes_directions():
    assert tp.mx(400) > tp.mx(390)  # +x right
    assert tp.my(300) > tp.my(400)  # PDF y grows down, plan +Y up


def test_one_metre_is_scale_pt(floorplan):
    assert tp.mx(floorplan["origin_pt"]["x"] + floorplan["scale"]["pt_per_m"]) == pytest.approx(
        1, rel=1e-3
    )


def test_rect_m_is_sorted():
    xmin, xmax, ymin, ymax = tp.rect_m([500, 400, 300, 200])
    assert xmin < xmax and ymin < ymax


def test_area_unit_square_and_orientation():
    sq = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert tp.area(sq) == pytest.approx(1)
    assert tp.area(sq[::-1]) == pytest.approx(1)


def test_mm_rounds_to_10mm():
    assert tp.mm(1.234) == "1230"
    assert tp.mm(0.9) == "900"


def test_room_areas_plausible():
    areas = {r["id"]: tp.area(r["poly"]) for r in tp.ROOMS}
    assert 20 < areas["living_kitchen"] < 40
    assert 8 < areas["bedroom"] < 20
    assert 2 < areas["bathroom"] < 8


def test_every_opening_has_geometry_and_height():
    for o in tp.OPENINGS:
        a, b, lo, hi, axis = tp.opening_geometry(o)
        assert b > a and hi > lo and axis in "xy", o["id"]
        head, _ = tp.opening_height(o)
        sill, _ = tp.opening_sill(o)
        assert 0 <= sill < head <= tp.CEIL, o["id"]
