"""Which points of data/electrical.json show as plates in the 3D model (plain Python, no Blender).

A point is drawn when it is a switch, socket, data or intercom point and nothing in data/furniture.json
stands in front of it. Points behind furniture (a socket behind the sofa, the hob outlet inside its cabinet)
are real but invisible, so no plate is built for them. A point may carry a "model" override ("at") where the
model puts it off its plan position; the point's note says why.
"""

PLATE_KINDS = {"socket", "socket2", "socket400", "data", "switch", "intercom"}
NORMAL_AXIS = {"+x": 0, "-x": 0, "+y": 1, "-y": 1}
TANGENT_MARGIN = 0.04  # half a plate: a plate partly behind an item counts as hidden
DEPTH_MARGIN = (
    0.10  # furniture within 10 cm of the wall, on the side the plate faces, stands in front of it
)


def pose(point):
    """(at, face) the model uses: the point's "model" override, else its plan position."""
    return point.get("model", {}).get("at", point["at"]), point["face"]


def hidden_by(point, items):
    """The id of an item that stands in front of the point, or None."""
    at, face = pose(point)
    n = NORMAL_AXIS[face]
    t = 1 - n
    sign = 1 if face[0] == "+" else -1
    front = sorted((at[n], at[n] + sign * DEPTH_MARGIN))  # the strip in front of the plate
    for it in items:
        if it["room"] == "balcony":
            continue
        x0, x1, y0, y1 = it["footprint"]
        lo, hi = ((x0, x1), (y0, y1))[n], ((x0, x1), (y0, y1))[t]
        z0, z1 = it["z"]
        if (
            lo[0] < front[1]
            and lo[1] > front[0]
            and hi[0] - TANGENT_MARGIN <= at[t] <= hi[1] + TANGENT_MARGIN
            and z0 <= point["h"] <= z1
        ):
            return it["id"]
    return None


def plates(points, items):
    """(visible, hidden): the points to build and {id: hiding item} for the ones behind furniture."""
    visible, hidden = [], {}
    for p in points:
        if p["kind"] not in PLATE_KINDS:
            continue
        by = hidden_by(p, items)
        if by:
            hidden[p["id"]] = by
        else:
            visible.append(p)
    return visible, hidden
