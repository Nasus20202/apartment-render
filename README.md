# Apartment render

A dimensionally accurate, photoreal Blender model of flat 19, building 18, Wiszące Ogrody (ul. Przytulna 1, Gdańsk, 2nd floor), built from `references/floor-plan.pdf`. The style is Scandinavian + Japandi with oak, forest-green accents and an openwork ("ażurowa") oak slat screen in the hall. Every object is generated from the JSON files in `data/`.

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
| Renders               | `make render` / `make evening` / `make preview` (one Blender process per view) | `renders/interior/`, `renders/preview/`                                 |

Requires Blender 5.2 (`make ... BLENDER=/path/to/blender`; the Fedora package currently can't load its OCIO config, see [usage](docs/usage.md#setup)) and `uv`. Run `uv sync` to install the Python tooling (pymupdf, pillow, matplotlib, ruff); `make lint` checks and `make fmt` fixes style with ruff; `make test` runs the unit tests. Cycles uses the GPU through HIP (`rocm-hip`) when available and falls back to the CPU otherwise. The `.blend` files are build outputs and are not in git: run `make all` (shell, layout, assets, interior, renders) to create them.

## Data (source of truth)

| File                   | Contents                                                                                                                                                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `data/floorplan.json`  | Walls, openings and rooms measured from the PDF vectors (scale bar 56.68 pt/m = 1:50), heights (ceiling 2.95 m, confirmed; anything not on the plan is flagged `"assumed": true`), orientation, installation points including the light outlets. |
| `data/furniture.json`  | Every furniture item: footprint, height, facing, generator or asset.                                                                                                                                                                             |
| `data/decor.json`      | Decor placements.                                                                                                                                                                                                                                |
| `data/electrical.json` | Sockets, switches, data, water and drain points on the walls, with heights; each is `plan` or `proposed`, with `h_assumed` where the height is not printed. Drawn on sheet 3 of the technical plan.                                              |
| `data/lighting.json`   | Ceiling fixtures, each hung on a light outlet from the installation plan.                                                                                                                                                                        |
| `data/cameras.json`    | Interior viewpoints with optional per-view exposure. `"lamps": true` lights windowless rooms in daytime shots.                                                                                                                                   |
| `data/site.json`       | Render date and time (drives the sun) and the courtyard seen from the windows.                                                                                                                                                                   |
| `data/assets.json`     | Third-party assets: Poly Haven models and HDRI, ambientCG materials (CC0), public-domain botanical prints from Wikimedia Commons.                                                                                                                |

Blender axes: origin at the inner south-west corner of the living room, +X to the right on the plan, +Y toward the top of the plan (the balcony side), Z up. True north is at 224.3° from +X (the balcony faces south-east), and the sun is computed for `data/site.json` `date_time`.

## Scripts

- `build_shell.py`: walls, openings, floors, ceilings, balcony; section-cut plan render.
- `build_layout.py`: placeholder blocks and clearance checks.
- `technical_plan.py`: dimensioned three-sheet A3 technical plan (dimensions, fit-out, services; PDF + PNG) from `data/*.json`; `make technical`.
- `materials.py`: PBR and procedural material library (box-projected, metric tile sizes).
- `furniture.py`: procedural generators (kitchen, peninsula + table, sofa, media wall, bed with draped bedding, wardrobes incl. the L-shaped hall one, partition, desk with two monitors and a PC, office chair, framed prints, walk-in shower, basin counter, sanitaryware and more). See [docs/furniture.md](docs/furniture.md).
- `build_interior.py`: finishes, doors, furniture, decor, curtains, lights from `lighting.json`, the balcony and courtyard, HDRI + sun, cameras, Cycles settings.
- `fetch_assets.py`: downloads `data/assets.json` into `assets/`.
- `render.py` / `modes.py`: batch rendering with day/evening lighting.

## Walking through it in Blender

Open `blender/apartment.blend`, set the viewport to _Material Preview_ or _Rendered_ (Z key), and look through `Cam_walk` (Numpad 0). Press **Shift + `** for Walk navigation: WASD to move, the mouse to look, **Tab** to toggle gravity, E/Q for up/down. For eye-height walking with gravity on by default, enable _Preferences → Navigation → Walk → Gravity_ and set the view height to 1.65 m.

## Collections

`Architecture/{Walls, Floors, Ceilings, Openings, Finishes, Doors}`, `Exterior`, `Furniture/<room>`, `Decor`, `Textiles`, `Lighting`, `Cameras_Lights`.
