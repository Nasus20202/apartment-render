# The flat

Flat 19, building 18, Wiszące Ogrody, ul. Przytulna 1, Gdańsk. It is on the 2nd floor (II piętro). The only source of truth is the developer's installation plan, `references/floor-plan.pdf` ("Karta instalacyjna", Załącznik DA-2a). The plan prints no dimensions ("Wymiary do odczytu wyłącznie ze skali"), so every length here is measured from the PDF's vector paths against its scale bar. The measurements are stored in `data/floorplan.json`, and everything in this document is derived from that file.

## Scale and coordinates

|                  |                                                                                                                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scale bar        | 0–3 m = 170.04 pt, so **56.68 pt/m** (nominal 1:50 on A3 is 56.69; they agree within 0.02 %)                                                                                           |
| Plan coordinates | PDF points on the displayed (rotated) page: x to the right, y down the page                                                                                                            |
| Blender frame    | metres; **origin at the inner south-west corner of the living room** (pt 354.0, 643.0); +X to the right on the plan, +Y up the plan (toward the balcony), Z up from the finished floor |
| Conversion       | `X = (x − 354.0) × 0.0176429`, `Y = (643.0 − y) × 0.0176429` (in `scripts/build_shell.py`)                                                                                             |

"South", "north" and the other directions in the code and these docs mean plan-down and plan-up, not compass directions. For the true compass, see [Orientation](#orientation-and-sun).

## Rooms

| Room                         | Floor area   | Extent in metres (X × Y)     | Notes                                                                                                                                                                                                            |
| ---------------------------- | ------------ | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Living room + kitchen + hall | 28.38 m²     | 0–5.155 × 0–6.295 (L-shaped) | One open space. The kitchen fills the south-west corner, the hall runs along the south wall to the bathroom, and the living room is to the north. The kitchen shaft (0.61 × 0.715 m) cuts the south-west corner. |
| Bedroom                      | 13.46 m²     | 4.153–6.994 × 3.103–7.841    | Window and balcony door are on the north side, the door from the hall is on the south.                                                                                                                           |
| Bathroom                     | 4.82 m²      | 5.293–6.994 × 0–2.990        | Windowless. The bath shaft (0.865 × 0.311 m) cuts the south-east corner.                                                                                                                                         |
| **Total**                    | **46.66 m²** |                              | Sum of the room polygons, not the official usable area                                                                                                                                                           |
| Balcony                      | 5.41 m²      | −0.088–3.793 × 6.722–8.116   | Off the living room. A privacy screen stands on the west end.                                                                                                                                                    |

## Heights

Heights are in `data/floorplan.json` → `heights_m`. A value marked _assumed_ is not printed on the plan. Change it in that file when the real number is known.

| Height                      | Value                            | Status                                                                                                 |
| --------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Ceiling (clear room height) | **2.95 m**                       | Confirmed by the owner, 2026-10-02                                                                     |
| Interior doors              | 0.90 × 2.10 m                    | Plan label 90/210                                                                                      |
| Entrance door               | 1.05 × 2.20 m                    | Plan label 105/220                                                                                     |
| Window head                 | 2.20 m                           | **Assumed** (bedroom window and door)                                                                  |
| Living-room glazing head    | 2.30 m                           | Set by the owner (2026-10-02)                                                                          |
| Bedroom window sill         | 0.50 m                           | **Assumed**. The plan only says "parapet obniżony" (lowered sill) with a low radiator.                 |
| Balcony floor               | −0.05 m below the interior floor | **Assumed**                                                                                            |
| Balcony railing             | 1.10 m                           | **Assumed** (standard minimum)                                                                         |
| Floor above the courtyard   | 6.8 m                            | **Assumed**. Ground floor raised ~0.3 m plus two storeys of ~3.25 m. It only affects the view outside. |

## Walls

| Wall                                                 | Type                                   | Thickness              |
| ---------------------------------------------------- | -------------------------------------- | ---------------------- |
| West and east (to the neighbours)                    | party                                  | 0.20 m                 |
| Living room north, bedroom north                     | exterior                               | 0.43 m, 0.37 m         |
| Bedroom west (by the balcony)                        | exterior                               | 0.36 m                 |
| South (to the corridor)                              | corridor                               | 0.24 m                 |
| Living room / bedroom, bedroom / hall, bathroom west | partitions (plasterboard per the plan) | 0.10 m, 0.11 m, 0.14 m |

## Openings

| Opening                | Width  | Span along its wall | Notes                                                |
| ---------------------- | ------ | ------------------- | ---------------------------------------------------- |
| Living room → balcony  | 2.60 m | X 0.552–3.155       | A fixed pane plus a pair of doors.                   |
| Bedroom window         | 1.50 m | X 4.825–6.327       | Lowered sill. A low radiator sits under it.          |
| Bedroom → balcony door | 0.90 m | Y 6.658–7.558       | Hinged on the north side and opens into the bedroom. |
| Entrance               | 1.05 m | X 2.904–3.956       | Hinged on the east side and opens inward.            |
| Bedroom door           | 0.90 m | X 4.203–5.102       | Hinged on the west side.                             |
| Bathroom door          | 0.90 m | Y 1.041–1.941       | Hinged on the south side and opens into the hall.    |

## Orientation and sun

The compass rose on the developer's arrangement plan (Hossa, "Propozycja aranżacji") puts north at the lower left of the drawing. True north is at **224.3° counter-clockwise from +X**, so the balcony and the bedroom window face **south-east** (bearing about 134°). The site is at latitude 54.36° N, longitude 18.52° E.

`scripts/build_interior.py` places the sun with an almanac formula for the time in `data/site.json`. The default is 2026-09-20 12:00 CEST, which puts the sun 36° high, shining in through the balcony from the right. Set a different `date_time` to see other seasons and times of day.

## Installation points

These are kept in `data/floorplan.json` → `fixtures_reference`, in plan points. They are reference positions for furnishing, not geometry.

| Point                                          | Blender position                                                                                     | Used for                                                                                                                                                                                                                                                         |
| ---------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ceiling light outlet **A**                     | (3.430, 1.204)                                                                                       | Hall LED strip                                                                                                                                                                                                                                                   |
| Ceiling light outlet **B**                     | (1.603, 1.790)                                                                                       | Kitchen: the LED strip turns here                                                                                                                                                                                                                                |
| Ceiling light outlet **CC1**                   | (2.028, 4.651)                                                                                       | Living room paper lantern                                                                                                                                                                                                                                        |
| Ceiling light outlet **DD1**                   | (5.574, 5.773)                                                                                       | Bedroom paper lantern                                                                                                                                                                                                                                            |
| Ceiling light outlet **E**                     | (5.981, 1.522)                                                                                       | Bathroom flush ceiling light                                                                                                                                                                                                                                     |
| Wall light outlet **E1**, h 2.30 m             | east bathroom wall, Y 1.653                                                                          | Light bar above the mirror                                                                                                                                                                                                                                       |
| Kitchen sink water and drain                   | west wall, Y ≈ 1.64                                                                                  | Sink at Y 1.35                                                                                                                                                                                                                                                   |
| Dishwasher socket (own circuit)                | west wall, Y ≈ 1.82                                                                                  | Full 60 cm dishwasher at the end of the south run (X 2.06–2.66); the cable runs behind the base cabinets and the water and drain from the sink                                                                                                                   |
| Hob 400 V outlet, hood socket h 2.00 m         | south wall, X ≈ 1.3                                                                                  | Hob and oven moved to X 1.76 so the fridge column is not next to the oven (a 25 cm small cabinet between); the 400 V and hood cables run from the outlets behind the cabinets. Hood under the south upper cabinets (the duct goes to the kitchen shaft)          |
| TV / SAT / internet and a socket               | living / bedroom partition, Y ≈ 5.3                                                                  | Media wall and TV                                                                                                                                                                                                                                                |
| Washbasin water                                | east bathroom wall, Y ≈ 1.64                                                                         | Basin at Y 1.62                                                                                                                                                                                                                                                  |
| WC frame                                       | south bathroom wall, X ≈ 5.72                                                                        | Wall-hung WC and boxing                                                                                                                                                                                                                                          |
| Washing machine water and socket h 0.70 m      | by the bath shaft                                                                                    | Machine at Y 0.32–0.92                                                                                                                                                                                                                                           |
| Fuse box (RM)                                  | south hall wall, X 4.78–5.10                                                                         | Inside the L-wardrobe, reached through its main doors                                                                                                                                                                                                            |
| Light switches A/B h 1.10 m, intercom h 1.60 m | south wall left of the entrance, X ≈ 2.75–2.79 (switches 15 cm from the opening, per the plan notes) | Built at X 2.78 (12 cm from the opening, clear of the 7 cm architrave) instead of the plan's 15 cm, so the wall beside the door stays free: the oak slat screen stands at X 2.66–2.73 and the kitchen's south run ends at X 2.66 (it was X 2.83), 17 cm shorter. |
| Radiators                                      | living room: tall, by the balcony door; bedroom: low, under the window; bathroom: white ladder       | Fixed by the developer                                                                                                                                                                                                                                           |

The developer lists elements that cannot be changed: steel panel radiators (and a white tube radiator in the bathroom), conglomerate stone sills, PVC windows, and concrete screeds. Partitions are plasterboard, and the plan's bathtub is drawn as a reference position only. This model replaces the bathtub with a walk-in shower.

## Changing the flat

1. Edit `data/floorplan.json`. Keep the plan-point coordinates, and add a `note` or `assumed: true` to anything that isn't measured from the PDF.
2. Run `make shell verify` and check `renders/shell_overlay.png` against the PDF.
3. Rebuild everything downstream: `make layout interior preview`.
