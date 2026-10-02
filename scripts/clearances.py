"""Layout clearance checks for data/furniture.json. Plain Python, so tests and CI can run it without Blender."""


def clearance_checks(items):
    """Return [(name, measured_m, required_m)] for the constraints that drive the layout.

    items: the "items" list of data/furniture.json. Every measured value must be >= its minimum.
    """
    f = {it["id"]: it["footprint"] for it in items}
    hob_at = next(it for it in items if it["id"] == "kitchen_base_south")["params"]["hob_at"]
    return [
        (
            "Fridge -> hob and oven (small cabinet between, 60 cm hob)",
            hob_at - 0.30 - f["fridge"][1],
            0.25,
        ),
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
        ("Slat screen -> intercom plate (model X 2.77)", 2.77 - f["slat_screen"][1], 0.02),
        ("Intercom plate -> entrance opening (X 2.904)", 2.904 - 2.87, 0.02),
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


def report_clearances(items):
    """Print the clearance report, so changes to furniture.json can be checked quickly. Returns the LOW count."""
    low = 0
    print("\n=== Layout clearances ===")
    for name, v, need in clearance_checks(items):
        ok = v >= need
        low += not ok
        print(f"  {'OK ' if ok else 'LOW'} {name:48s} {v:5.2f} m  (min {need:.2f})")
    return low
