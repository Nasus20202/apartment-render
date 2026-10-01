# How to use it

## Setup

| Need          | Notes                                                                                                                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Blender 5.2   | The portable build at `~/.local/opt/blender-5.2.2-linux-x64/blender` is known to work (Cycles on HIP, RX 5700). Pass it with `make ... BLENDER=/path/to/blender` or set `BLENDER` in your environment. |
| GPU           | Optional. Cycles tries OptiX, CUDA, HIP and oneAPI in that order and falls back to the CPU. On AMD, install `rocm-hip`.                                                                                |
| `uv`          | Python tooling: `uv sync` installs pymupdf, pillow, matplotlib and ruff.                                                                                                                               |
| Network, once | `make assets` downloads about 420 MB of CC0 / public-domain assets into `assets/`.                                                                                                                     |

> **Fedora's `blender` package (5.2.2-1.fc44):** it links OpenColorIO 2.4.2 but ships Blender 5.2's OCIO 2.5 config. Colour management falls back to "Standard", and `make interior` stops with `enum "AgX" not found`. Until Fedora rebuilds it, run the portable build: `make interior render BLENDER=~/.local/opt/blender-5.2.2-linux-x64/blender`.

## The pipeline

```
make shell      # walls, openings, floors from data/floorplan.json   -> blender/apartment_shell.blend
make verify     # overlay the plan render on the PDF                   -> renders/shell_overlay.png
make layout     # furniture placeholders + clearance report            -> renders/layout_proposal.png
make assets     # download assets (idempotent)                         -> assets/
make interior   # furnished, lit scene                                 -> blender/apartment.blend
make preview    # every view at half size, 48 samples (~35 s each)     -> renders/preview/
make render     # every view at 1800x1200, 512 samples + the furnished plan -> renders/interior/
make evening    # evening views, lamps on                              -> renders/interior/*_evening.png
make all        # shell layout assets interior render
```

Each step reads only the data files and the previous step's output, so the edit cycle is:

1. Edit `data/*.json` (and `scripts/` for new kinds of objects).
2. `make layout` if footprints moved. Read the clearance report: every line should say `OK`.
3. `make interior`.
4. Render one view to check it: `blender -b blender/apartment.blend -P scripts/render.py -- --cams bedroom_bed --samples 48 --scale 50 --out renders/preview`.
5. `make render evening` for the finals.

`make lint` checks the scripts with ruff, and `make fmt` fixes and formats them.

## Rendering

`scripts/render.py` options, after `--`:

| Option                | Default                    |                                                                   |
| --------------------- | -------------------------- | ----------------------------------------------------------------- |
| `--cams a,b`          | every camera except `walk` | `none` renders no views (use with `--plan`)                       |
| `--samples N`         | 256                        | Makefile targets pass 512 (`SAMPLES=`)                            |
| `--scale PCT`         | 100                        | Percentage of 1800 × 1200                                         |
| `--mode day\|evening` | day                        | Evening turns the sun off, dims the sky and switches the lamps on |
| `--out DIR`           | `renders/interior`         |                                                                   |
| `--plan`              | off                        | Also renders the furnished top-down plan                          |

The Makefile starts **one Blender process per view**. On the 8 GB RX 5700, HIP crashes with "Memory access fault by GPU" after a few renders in one process, so don't render several cameras in one call for the finals. To render a subset, run `make render CAMS="bedroom_bed bathroom_vanity"`.

### Cameras (`data/cameras.json`)

```json
"bedroom_bed": { "loc": [4.4, 5.25, 1.45], "target": [7.0, 5.25, 1.4], "lens": 17, "shift_y": -0.02, "exposure": 2.6 }
```

`loc` and `target` are world metres. Cameras are kept level and yaw toward the target, so vertical lines stay vertical. Use `shift_y` to frame higher or lower instead of tilting. `lens` is in mm on a 36 mm sensor (16–20 mm suits these rooms). `exposure` overrides the scene's 2.0 EV, which interiors under the real sun need. `"lamps": true` switches the lamps on in daylight, for the windowless bathroom and hall. `walk` is for walking around in Blender and is never rendered.

Current views: `living_hero`, `living_tv`, `living_balcony`, `balcony`, `kitchen_island`, `kitchen_u`, `hall_entrance`, `hall_kitchen`, `bedroom_door`, `bedroom_window`, `bedroom_bed`, `bedroom_desk`, `bathroom_shower`, `bathroom_vanity`.

### Sun and time of day

`data/site.json` → `date_time` (ISO with timezone) sets the sun from the real orientation of the flat (see [flat.md](flat.md#orientation-and-sun)). The HDRI is rotated to match. Rebuild with `make interior`.

## Common changes

| To...                     | Edit                                                                                                                                                                                                        |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Move or resize furniture  | `footprint` / `z` in `data/furniture.json`, then `make layout interior`                                                                                                                                     |
| Add a piece of furniture  | A new line in `furniture.json` with an existing generator (see [furniture.md](furniture.md)), or a Poly Haven model: add it to `data/assets.json`, run `make assets`, then use `"source": "polyhaven:<id>"` |
| Add a plant, vase or book | `data/decor.json`                                                                                                                                                                                           |
| Change a colour or finish | `params` (`material`, `front`, `table_material`) to another material key, or the material itself in `scripts/materials.py`                                                                                  |
| Move a light              | `data/lighting.json`. Fixtures name their outlet from the installation plan. Moving one off its outlet means a new cable, so write that in its `note`.                                                      |
| Add a view                | `data/cameras.json`; `make interior` creates `Cam_<name>`                                                                                                                                                   |
| Confirm an assumed height | `data/floorplan.json` → `heights_m`: set the value, `"assumed": false`, and a note with the source. Then `make shell layout interior`.                                                                      |

## Walking through it in Blender

Open `blender/apartment.blend`, switch the viewport to _Material Preview_ or _Rendered_ (Z), and look through `Cam_walk` (Numpad 0). **Shift + `** starts walk navigation: WASD to move, the mouse to look, Tab toggles gravity, E/Q for up and down. To walk at eye height with gravity on, set _Preferences → Navigation → Walk → Gravity_ and a 1.65 m view height.

## Troubleshooting

| Symptom                                | Cause, fix                                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `enum "AgX" not found in ('Standard')` | The Blender can't load its OCIO config. See the Fedora note above.                                |
| `Memory access fault by GPU`           | Several renders in one HIP process. Render one camera per process, as the Makefile does.          |
| Black patches on furniture             | Two boxes overlap with coplanar faces. Make parts butt against each other instead of overlapping. |
| A Poly Haven model is missing          | `make assets` (the console prints `FAILED <id>` for downloads that failed)                        |
| The interior looks dark by day         | Realistic: the balcony roof shades the living room. Raise that camera's `exposure`.               |
