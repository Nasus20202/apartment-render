import wall_points as wp


def test_switch_and_intercom_sit_on_the_wall_beside_the_entrance(electrical, items):
    visible, _ = wp.plates(electrical["points"], items)
    by_id = {p["id"]: p for p in visible}
    screen = next(it for it in items if it["id"] == "slat_screen")
    for pid in ("H1", "H2"):
        at, face = wp.pose(by_id[pid])
        assert face == "+y" and at[1] == 0.0, "on the south wall, facing into the hall"
        assert at[0] - 0.04 > screen["footprint"][1], (
            "the slat screen must stand clear of the plate"
        )
        assert at[0] + 0.04 < 2.904 - 0.07, "and the plate must clear the entrance architrave"


def test_points_behind_furniture_are_not_built(electrical, items):
    _, hidden = wp.plates(electrical["points"], items)
    assert (
        hidden["S2"] == "floor_lamp_living" and hidden["B1"] == "bed" and hidden["K5"] == "fridge"
    )


def test_splashback_sockets_are_visible(electrical, items):
    visible, _ = wp.plates(electrical["points"], items)
    assert {"K6", "K7"} <= {p["id"] for p in visible}


def test_water_and_light_points_have_no_plate(electrical, items):
    visible, hidden = wp.plates(electrical["points"], items)
    kinds = {p["kind"] for p in visible} | {
        p["kind"] for p in electrical["points"] if p["id"] in hidden
    }
    assert kinds <= wp.PLATE_KINDS
