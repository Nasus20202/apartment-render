# Furniture, decor, lights and materials

All the furnishing is data. The scripts read four files, and the model is rebuilt from scratch on every `make interior`:

| File                   | What it holds                                                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- |
| `data/furniture.json`  | Every built-in and piece of furniture: footprint, height, facing, and the generator or asset that builds it |
| `data/decor.json`      | Small objects placed by their base point: plants, vases, books, lamps                                       |
| `data/lighting.json`   | Ceiling fixtures, hung on the developer's light outlets                                                     |
| `data/electrical.json` | Wall sockets, switches, data and water points (technical plan only; the 3D model doesn't use it)            |
| `data/cameras.json`    | Viewpoints for the renders                                                                                  |

Coordinates are metres in the Blender frame (see [flat.md](flat.md#scale-and-coordinates)): origin at the inner south-west corner of the living room, +X right, +Y up the plan, Z up from the finished floor.

## `furniture.json` items

The file is formatted by hand with one item per line. Edit it as text; rewriting it with `json.dump` destroys the layout.

```json
{
  "id": "bed",
  "room": "bedroom",
  "cat": "bed",
  "label": "Bed 160x200",
  "footprint": [4.99, 6.99, 4.45, 6.05],
  "z": [0, 0.95],
  "facing": "-x",
  "source": "proc:bed",
  "params": {}
}
```

| Field       | Meaning                                                                                                                                        |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`        | Unique name. It becomes the Blender object name and is how `build_layout.py` clearance checks refer to the item.                               |
| `room`      | Collection `Furniture_<room>`: `kitchen`, `living`, `hall`, `bedroom`, `bathroom`, `balcony`                                                   |
| `cat`       | Colour class on the layout plan: `kitchen`, `kitchen_upper`, `table`, `seat`, `rug`, `storage`, `tv`, `bed`, `bath`, `boxing`, `decor`, `wall` |
| `label`     | Text on the layout plan (empty for none)                                                                                                       |
| `footprint` | `[xmin, xmax, ymin, ymax]` on the floor                                                                                                        |
| `z`         | `[bottom, top]`. Most generators read only the top.                                                                                            |
| `facing`    | Direction the front faces: `+x`, `-x`, `+y`, `-y`. The back stands against the opposite side of the footprint.                                 |
| `source`    | `proc:<generator>` (procedural, below) or `polyhaven:<asset id>` (centred on the footprint, standing at `z[0]`)                                |
| `params`    | Generator options (below)                                                                                                                      |
| `base_z`    | Optional vertical offset of the whole item, e.g. `-0.03` on the balcony, which is a step down                                                  |

Each generator builds in a local frame of width `w` along +X and depth `d` along +Y, with the front at `y = 0`. `place()` then rotates and moves it onto the footprint. Generators listed in `WORLD_SPACE` (`walkin_shower`, `l_wardrobe`) build straight in world coordinates. Any parameter that names a world position (`sink_at`, `basin_at`, ...) is given in world metres along the item's width axis.

### Generators and their parameters

**Kitchen**

| Generator      | Builds                                                               | Parameters                                                                                                                                                                           |
| -------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `kitchen_run`  | Base cabinets, worktop, splashback                                   | `sink_at` (world, undermount sink and tap), `hob_at` (world), `oven_under_hob` (bool), `dishwasher` `[a, b]`, `small_door` `[a, b]`. The rest is filled with drawer stacks.          |
| `tall_unit`    | Floor-to-top column with a filler to the ceiling                     | `fridge` (integrated fridge, top-box door above 2.10 m) or `oven`                                                                                                                    |
| `upper_run`    | Wall cabinets with an LED strip underneath                           | `hood_at` (world). Taller than 1 m gives two rows of doors.                                                                                                                          |
| `peninsula`    | Base cabinets that continue into a dining table with a waterfall end | `cabinets_to`, `cabinet_depth` (0.6), optional `dishwasher` `[a, b]` (plain drawer stacks without it), `top_thickness` (0.06), `table_height`, `table_material` (`oak` or `worktop`) |
| `open_shelves` | Plain oak shelves                                                    | `count` (2)                                                                                                                                                                          |
| `dining_chair` | Oak chair with a woven-look seat                                     | none                                                                                                                                                                                 |

**Living room**

| Generator        | Builds                                                                                                 | Parameters                                                                                                                                                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `sofa`           | Sofa with an optional chaise on its south end, throw pillows and a throw (one seat cushion per ~0.8 m) | `fabric` (material key, default `sofa_fabric`; the living room uses `velvet_green`), `body_depth` (seat depth of the main body; the rest of the item depth is the chaise), `chaise_w` (chaise width along the wall; 0 = none), `chaise_end` (`south`, the default, or `north`) |
| `ottoman`        | Footrest                                                                                               | `round` (drum pouf), `material` (default `boucle`; the living room uses `velvet_green` to match the sofa)                                                                                                                                                                      |
| `rug`            | Wool rug                                                                                               | none                                                                                                                                                                                                                                                                           |
| `media_wall`     | Built-in oak TV wall: two towers with niches, a hanging console, a bridge cabinet, a green panel       | `tower_width` (0.50), `console_z` `[z0, z1]`, `bridge_z0`; towers and bridge run up to the item's `z[1]` (the living room sets the full ceiling height 2.95), niche shelves every 0.45 m                                                                                       |
| `tv`             | Flat screen                                                                                            | none                                                                                                                                                                                                                                                                           |
| `tv_console`     | Slatted oak sideboard on legs                                                                          | `doors` (4)                                                                                                                                                                                                                                                                    |
| `floating_shelf` | One oak shelf                                                                                          | none                                                                                                                                                                                                                                                                           |
| `floor_lamp`     | Paper floor lamp with a light                                                                          | none                                                                                                                                                                                                                                                                           |

**Hall and partitions**

| Generator      | Builds                                                                                                                                                                      | Parameters                                                                                                                                                                                             |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `open_unit`    | Free-standing oak tower in the media wall's style: closed slat-door bays and open see-through bays stacked from the plinth to the top                                       | `levels`: list of `[z0, z1, "closed"\|"open"]`                                                                                                                                                         |
| `slat_screen`  | Openwork ("ażur") divider: vertical slats floor to ceiling on floor and ceiling rails                                                                                       | `material` (`oak`), `slat_width` (0.04), `gap` (0.03), `remove`                                                                                                                                        |
| `partition`    | Floor-to-ceiling plasterboard wall with skirting                                                                                                                            | `material` (a key from the material library, e.g. `paint_green`), `skirting` (`["front", "back"]`), `remove` (shell object names it replaces, e.g. an architrave it would swallow)                     |
| `l_wardrobe`   | L-shaped corner wardrobe (world space). The main run stands on the footprint's ymin wall. The return stands on its xmax wall, with an open shoe niche and a door facing -X. | `main_depth` (0.60), `return_depth` (0.40), `split_z` (2.25, start of the top boxes), `shoe_niche` (0.42)                                                                                              |
| `wardrobe`     | Built-in wardrobe; above 2.45 m it gets top-box doors from `split_z`                                                                                                        | `doors` (2), `sliding` (bool), `mirror` (`true` or `"smoked"`, full-height mirror sliding doors, no top boxes; two leaves, one in front and one behind, each sliding past the other), `split_z` (2.25) |
| `mirror`       | Oak-framed wall mirror                                                                                                                                                      | none                                                                                                                                                                                                   |
| `divider_wall` | Short plastered wall (not used at the moment)                                                                                                                               | none                                                                                                                                                                                                   |

**Bedroom**

| Generator       | Builds                                                                                                            | Parameters                                                                                |
| --------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `bed`           | Oak platform bed, linen headboard, draped duvet. Pillows and cushions are dropped onto the sheet with `settle()`. | none                                                                                      |
| `standing_desk` | Sit-stand desk with two 27" monitors on a dual arm, a small-form-factor PC, keyboard and mouse                    | `monitors_x` (local x of the arm), `monitor_angle` (12°), `pc_x` `[x0, x1]` (local)       |
| `office_chair`  | Task chair: five-star base, gas lift, mesh back, armrests                                                         | none                                                                                      |
| `desk_chair`    | Dining chair with a cushion (the previous desk chair)                                                             | none                                                                                      |
| `art_print`     | Framed print: oak frame, mount, an image from `assets/images/` cropped to the opening                             | `image` (key in `assets.json` `images`), `frame` (0.02), `mount` (0.05), `frame_material` |

**Bathroom**

| Generator                                       | Builds                                                                                                        | Parameters                                                                                                                                                                                                                                                                                                                                         |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `walkin_shower`                                 | Tray, fixed glass, rain head on a wall arm, thermostatic mixer, hand shower                                   | `glass_from_x`, `head_at` `[x, y]`, `head_z` (2.20)                                                                                                                                                                                                                                                                                                |
| `bath_counter`                                  | Oak worktop over the washing machine and the vanity, inset ceramic basin with a deck mixer, mirror, light bar | `basin_at` (world), `cabinet` `[a, b]` (world), `cabinet_bottom` (0.42), `top` (worktop material, default `stone_resin`, white), `front` (vanity drawers, default `oak_rich`), `wood` (worktop, carcass, frame; default `oak_rich`), `top_z` (0.90), `mirror_width` (0.60), `mirror_z` `[z0, z1]`, `light_at` (world, outlet E1), `light_z` (2.30) |
| `wall_cabinet`                                  | Wall-hung cupboard                                                                                            | `doors` (2), `front` (`oak`), `shelf_below` (gap in metres to an open shelf under it)                                                                                                                                                                                                                                                              |
| `washing_machine`, `wc`, `boxing`, `towel_rail` | Sanitaryware, WC frame boxing with an oak shelf, ladder rail with a towel                                     | none                                                                                                                                                                                                                                                                                                                                               |

**Balcony**

| Generator                      | Builds                                         | Parameters |
| ------------------------------ | ---------------------------------------------- | ---------- |
| `bistro_table`, `bistro_chair` | Round smoked-oak table, folding slatted chairs | none       |

## What is in the flat now

| Room        | Items                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Kitchen     | U kitchen: sink run on the west wall, hob and oven run on the south wall, fridge column, wall cabinets up to 2.85 m. A 70 cm deep peninsula on the north side turns into the oak dining table, with 4 chairs.                                                                                                                                                                                                                                                                     |
| Hall        | **Openwork oak slat screen** ("ażurowa ściana", X 2.66–2.73, Y 0–1.041, set back so the light switches and intercom fit on the wall beside the entrance, mirroring the bathroom wall from the corner to the bathroom door, floor to ceiling, 4 cm slats with 3 cm gaps) between the kitchen and the entrance. **L-wardrobe** (X 4.03–5.155, Y 0–0.96) on the right as you come in, with top boxes to the ceiling and a shoe niche in the return. Oak mirror by the bathroom door. |
| Living room | 255 cm velvet sofa (no sideboard), matching round footrest, rug, oak media wall to the ceiling with the TV, continued south by a see-through oak unit (closed cabinets, open shelf bays with plants) beside the bedroom-door passage, floor lamp by the window, two staggered high oak shelves above the sofa with a framed print, books, vases and a plant                                                                                                                       |
| Bedroom     | 160 × 200 bed, smoked-mirror sliding wardrobe, nightstand and bedside shelf, a triptych of **botanical prints** above the bed, **three floating shelves** above the desk end, standing desk with **two monitors and an SFF PC**, **office chair**, plant in the corner between the nightstand and the desk                                                                                                                                                                        |
| Bathroom    | Walk-in rain shower with a forest-green **hexagon-tiled** back wall and a graphite hexagon tray. **Oak worktop over the washing machine and an oak floating vanity**, inset **classic ceramic basin**, mirror centred on the basin, light bar on outlet E1, **oak wall cabinet over the washing machine** with an open shelf, WC boxing with an oak shelf, ladder rail                                                                                                            |
| Balcony     | Bistro table, two chairs, two potted plants                                                                                                                                                                                                                                                                                                                                                                                                                                       |

## `decor.json`

```json
{
  "asset": "polyhaven:potted_plant_02",
  "at": [6.76, 6.84, 0.0],
  "rot": 40,
  "scale": 0.6
}
```

`at` is the base centre `[x, y, z]`, where `z` is the top of the surface the object stands on. `rot` is in degrees about Z, and 0 means the model's front faces -Y (use -90 for a wall on +X with the object facing -X). `scale` is uniform. `"proc:table_lamp"` builds a ceramic table lamp with a light inside.

## `lighting.json`

Each fixture names the outlet it hangs on (A, B, CC1, DD1, E, E1 in `floorplan.json` → `fixtures_reference.light_outlets`), so the lights match the electrical plan.

| Type             | Fields                                                                                                                                                                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `led_strip`      | `outlets` [first, second], `start_y`, `end_x`, `width`, `w_per_m`. The path is (first.x, start_y) → (first.x, second.y) → (end_x, second.y): a recessed profile from the entrance through A, a 90° turn, then through B into the kitchen. |
| `globe_pendants` | `at` [[x, y], ...], `bottom_z`, `w`. The Poly Haven globes' cords are lengthened to the real ceiling. They are **not** on an outlet and need a cable run from B.                                                                          |
| `lantern`        | `outlet`, `radius`, `centre_z`, `w`: paper lantern pendant                                                                                                                                                                                |
| `flush_disc`     | `outlet`, `radius`, `w`: flush opal ceiling light                                                                                                                                                                                         |

The wall light over the bathroom mirror (outlet E1) is part of the `bath_counter` item. Lamps carry `role = "lamp"`, and `scripts/modes.py` switches them on in the evening only.

## Materials (`scripts/materials.py`)

`library()` returns a dict, and the keys are what `params` such as `material`, `front` or `table_material` accept. Textured materials are box-projected in object space with metric tile sizes, so procedural meshes need no UVs. The exception is `art_print`, which builds its own UVs.

| Key                                                                                                                            | Look                                                                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `oak`, `oak_dark`                                                                                                              | Light oak veneer, smoked oak (ambientCG Wood094)                                                                                    |
| `front_white`, `front_greige`                                                                                                  | Matte lacquered fronts                                                                                                              |
| `worktop`                                                                                                                      | Honed marble (Marble012)                                                                                                            |
| `wall`, `wall_accent`, `paint_green`                                                                                           | Matte paints over a faint plaster relief.                                                                                           |
| `bath_wall_x`, `bath_wall_y`                                                                                                   | Large-format (60 × 30 cm) white glossy wall tiles (Plaster001 base), for walls along X and along Y                                  |
| `hex_green`, `hex_floor`                                                                                                       | Glazed hexagons (10 cm corner to corner), generated mask from `hex_tiles()`: forest green on the shower back wall, grey on the tray |
| `oak_rich`                                                                                                                     | Warm oak with visible grain (WoodFloor062), used in the bathroom                                                                    |
| `bath_floor`                                                                                                                   | 60 × 60 plain light-grey matte floor tiles (Plaster001 base)                                                                        |
| `sofa_fabric`, `boucle`, `linen`, `linen_sage`, `linen_green`, `velvet_green`, `cotton_white`, `fabric_charcoal`, `mesh_black` | Textiles                                                                                                                            |
| `ceramic`, `stone_resin`, `black_metal`, `graphite`, `steel`, `chrome`, `glass`, `mirror`, `led`, `bulb`                       | Everything else                                                                                                                     |

## Assets

`data/assets.json` lists the third-party assets: Poly Haven models and HDRI (CC0), ambientCG materials (CC0), and public-domain botanical plates from Wikimedia Commons (Meehan, _The Native Flowers and Ferns of the United States_, 1878–79). `make assets` downloads them into `assets/`, which is gitignored.
