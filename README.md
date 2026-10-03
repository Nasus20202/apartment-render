# Apartment render

A dimensionally accurate, photoreal Blender model of flat 19, building 18, Wiszące Ogrody (ul. Przytulna 1, Gdańsk, 2nd floor), built from `references/floor-plan.pdf`. The style is Scandinavian + Japandi with oak, forest-green accents and an openwork ("ażurowa") oak slat screen in the hall. Every object is generated from the JSON files in `data/`.

## Renders

A selection of the views. Day views are natural sunlight only, evening views are lit by the lamps. The kitchen and the windowless bathroom are dark by day, so they are shown in the evening. Click an image for the lossless PNG. The **Render** workflow builds every view and publishes them (PNG and JPG), with the plans, as the latest [release](https://github.com/Nasus20202/apartment-render/releases/latest).

| Day | Evening |
| --- | --- |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_hero.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_hero.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_hero_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_hero_evening.jpg" width="420"></a> |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_door.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_door.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_door_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_door_evening.jpg" width="420"></a> |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_window.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_window.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_window_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/bedroom_window_evening.jpg" width="420"></a> |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_from_kitchen.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_from_kitchen.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_from_kitchen_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_from_kitchen_evening.jpg" width="420"></a> |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_unit.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_unit.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_unit_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/living_unit_evening.jpg" width="420"></a> |

| Evening | |
| --- | --- |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/kitchen_island_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/kitchen_island_evening.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/hall_kitchen_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/hall_kitchen_evening.jpg" width="420"></a> |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/bathroom_shower_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/bathroom_shower_evening.jpg" width="420"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/bathroom_vanity_evening.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/bathroom_vanity_evening.jpg" width="420"></a> |

| Dimensions | Fit-out | Services |
| --- | --- | --- |
| <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan_dimensions.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan_dimensions.png" width="280" alt="Dimensioned plan"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan_fitout.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan_fitout.png" width="280" alt="Fit-out plan"></a> | <a href="https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan_services.png"><img src="https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan_services.png" width="280" alt="Services plan"></a> |

The three technical plan sheets (A3, 1:40). Also: [technical plan (PDF)](https://github.com/Nasus20202/apartment-render/releases/latest/download/technical_plan.pdf), [furnished plan](https://github.com/Nasus20202/apartment-render/releases/latest/download/plan_furnished.png). Every release also has three zips: `renders-png.zip` (all views, lossless), `renders-jpg.zip` (all views, small) and `plans.zip` (technical plan PDF and PNGs, furnished plan, layout proposal, shell overviews).

| Docs                                   |                                                                                                                            |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| [docs/usage.md](docs/usage.md)         | Setup, the make targets, rendering, cameras, common edits, troubleshooting                                                 |
| [docs/flat.md](docs/flat.md)           | The flat's parameters: scale, rooms and areas, heights (confirmed and assumed), openings, orientation, installation points |
| [docs/furniture.md](docs/furniture.md) | Furniture, decor, lighting and camera schemas, every generator and its parameters, materials                               |
| [AGENTS.md](AGENTS.md)                 | Rules and conventions for AI coding agents                                                                                 |

## Pipeline

```
make all        # shell -> layout -> assets -> interior -> render
```

| Step                  | Command                                                                        | Output                                                                  |
| --------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------------- |
| Shell                 | `make shell`                                                                   | `blender/apartment_shell.blend`, `renders/shell_topdown.png`, overviews |
| Check against the PDF | `make verify`                                                                  | `renders/shell_overlay.png`                                             |
| Furniture layout      | `make layout`                                                                  | `renders/layout_proposal.png` + clearance report                        |
| Assets                | `make assets`                                                                  | `assets/` (CC0, gitignored, ~420 MB)                                    |
| Interior              | `make interior`                                                                | `blender/apartment.blend`                                               |
| Technical plan        | `make technical`                                                               | `renders/technical_plan.pdf` + PNGs (no Blender)                        |
| Renders               | `make render` / `make evening` / `make preview` (one Blender process per view); finals also via the **Render** workflow, published as releases | `renders/` (untracked)                                 |

Requires Blender 5.2 (`make ... BLENDER=/path/to/blender`; the Fedora package can't load its OCIO config, see [usage](docs/usage.md#setup)) and `uv` (`uv sync`). Cycles uses the GPU through HIP when available and falls back to the CPU. The `.blend` files are build outputs and are not in git. `make lint`, `make fmt` and `make test` need no Blender. To walk through the result, see [usage](docs/usage.md#walking-through-it-in-blender).

## Data (source of truth)

| File                   | Contents                                                                                                                                                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `data/floorplan.json`  | Walls, openings and rooms measured from the PDF vectors (scale bar 56.68 pt/m = 1:50), heights (ceiling 2.95 m, confirmed; anything not on the plan is flagged `"assumed": true`), orientation, installation points including the light outlets. |
| `data/furniture.json`  | Every furniture item: footprint, height, facing, generator or asset.                                                                                                                                                                             |
| `data/decor.json`      | Decor placements.                                                                                                                                                                                                                                |
| `data/electrical.json` | Sockets, switches, data, water and drain points on the walls, with heights; each is `plan` or `proposed`, with `h_assumed` where the height is not printed. Drawn on sheet 3 of the technical plan.                                              |
| `data/lighting.json`   | Ceiling fixtures, each hung on a light outlet from the installation plan.                                                                                                                                                                        |
| `data/cameras.json`    | Interior viewpoints (location, target, lens, vertical shift).                                                                                                                                                                                 |
| `data/site.json`       | Render date and time (drives the sun) and the courtyard seen from the windows.                                                                                                                                                                   |
| `data/assets.json`     | Third-party assets: Poly Haven models and HDRI, ambientCG materials (CC0), public-domain botanical prints from Wikimedia Commons.                                                                                                                |

Blender axes: origin at the inner south-west corner of the living room, +X to the right on the plan, +Y toward the top of the plan (the balcony side), Z up. True north is at 224.3° from +X (the balcony faces south-east), and the sun is computed for `data/site.json` `date_time`.

## Scripts

- `build_shell.py`: walls, openings, floors, ceilings, balcony; section-cut plan render.
- `build_layout.py` / `clearances.py`: placeholder blocks and clearance checks.
- `technical_plan.py`: dimensioned three-sheet A3 technical plan (dimensions, fit-out, services; PDF + PNG) from `data/*.json`; `make technical`.
- `materials.py`: PBR and procedural material library (box-projected, metric tile sizes).
- `furniture.py`: procedural generators (kitchen, peninsula + table, sofa, media wall, bed with draped bedding, wardrobes incl. the L-shaped hall one, partition, desk with two monitors and a PC, office chair, framed prints, walk-in shower, basin counter, sanitaryware and more). See [docs/furniture.md](docs/furniture.md).
- `build_interior.py`: finishes, doors, furniture, decor, curtains, lights from `lighting.json`, the balcony and courtyard, HDRI + sun, cameras, Cycles settings.
- `fetch_assets.py`: downloads `data/assets.json` into `assets/`.
- `render.py` / `modes.py`: batch rendering with day/evening lighting.
- `verify_overlay.py` / `plan_tiles.py`: check the shell against the PDF; plot PDF vectors on a grid (`make tiles`).

## Collections

`Architecture/{Walls, Floors, Ceilings, Openings, Finishes, Doors}`, `Exterior`, `Furniture/<room>`, `Decor`, `Textiles`, `Lighting`, `Cameras_Lights`.
