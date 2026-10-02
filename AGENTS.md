# AGENTS.md

Guidance for AI coding agents working in this repository. Read [README.md](README.md) first, then [docs/usage.md](docs/usage.md) (pipeline and rendering), [docs/flat.md](docs/flat.md) (the apartment's measured parameters) and [docs/furniture.md](docs/furniture.md) (data schemas and generators).

## What this is

This is a photoreal, dimensionally accurate Blender model of a real flat, built for its owner to plan the fit-out. Python scripts run inside Blender build every object from the JSON files in `data/`. There is no hand-modelled geometry, and `.blend` files are build outputs.

## Rules

1. **The floor plan is the source of truth.** `references/floor-plan.pdf` has no printed dimensions, so lengths come from its vectors at 56.68 pt/m (`data/floorplan.json`). Never invent a dimension silently. Anything not measured from the plan or confirmed by the owner gets `"assumed": true` and a `note` in `floorplan.json`, or a note in the item, and goes into your report to the owner.
2. **Change the data, not the .blend.** Positions, sizes and choices belong in `data/*.json`; new kinds of objects belong in a generator in `scripts/furniture.py`. Rebuild with `make interior`. Hand edits to `blender/apartment.blend` are lost on the next build.
3. **Respect the installation plan.** Lights hang on the developer's outlets (`fixtures_reference.light_outlets`, via `data/lighting.json`). Sinks, the WC and the washing machine sit on their water and drain points, and the media wall sits on the TV/SAT socket. If a design moves something off its point, say so in a `note` and in your report (for example, the dining pendants need a cable from outlet B).
4. **Keep clearances.** After moving footprints, run `make layout`. Every line of the clearance report must say `OK`. Add a check to `clearance_checks()` in `scripts/clearances.py` for each new constraint you introduce; `make test` also fails on any `LOW` line.
5. **Check renders before claiming a result.** Render the affected views (one process per view, see below), look at them, and fix what is wrong. Typical faults: floating objects (use `settle()` for soft things), objects inside walls, black patches from coplanar overlapping boxes, lamps not lined up with their fixtures.
6. **Report honestly.** List what changed, every assumption you made, and anything you could not verify or render.

## Conventions

- **Coordinates:** metres; origin at the inner south-west corner of the living room; +X right, +Y up the plan (toward the balcony); Z up from the finished floor. "North" in names means plan-up. True north is at 224.3° counter-clockwise from +X.
- **`data/furniture.json` is hand-formatted, one item per line.** Edit it as text with exact string replacements. Loading and dumping it with `json` rewrites the whole layout. `cameras.json` and `decor.json` are plain `indent=2` JSON.
- **Generators** build in a local frame (width along +X, depth along +Y, front at y = 0) and are placed by `place()`. Parameters that are world positions are given in world metres and converted with `world_to_local_x()`. The ceiling height is `F.CEIL`; never hard-code 2.65 or 2.95.
- **Materials** come from `materials.library()` and are box-projected in metric object space. Build objects at true size with unit scale.
- **Python style:** ruff, line length 100 (`make lint`, `make fmt`). Match the surrounding code: short docstrings that say what is built and why, few comments.
- **Assets:** `data/assets.json` lists only CC0 or public-domain assets, fetched by `scripts/fetch_assets.py` into `assets/` (gitignored). Don't commit assets.

## Running Blender

- Use a Blender 5.2 build with working OpenColorIO 2.5: `make <target> BLENDER=~/.local/opt/blender-5.2.2-linux-x64/blender`. The Fedora `blender` package can't load its own OCIO config ("AgX not found").
- Render **one camera per Blender process** for finals. HIP on the 8 GB card faults after a few renders in one process. The Makefile already loops per camera. `make preview` is the exception: it runs `PREVIEW_CHUNK` (4) views per process with persistent data. If a preview run faults, lower `PREVIEW_CHUNK`.
- Previews: `--samples 48 --scale 50` take about 35 s a view. Finals: the Makefile default of 256 samples (adaptive, with OpenImageDenoise) at full size; don't lower `SAMPLES` for a final set. Run long jobs in the background and don't restart them automatically if they are killed.
- Kill stray renders by PID (`pgrep -f "blender -b"`). `pkill -f '<pattern>'` also matches the shell that runs it.

## Before you commit

- `make lint` is clean and `make test` passes (no Blender needed; CI runs both on every push and pull request).
- `make layout` reports all `OK`.
- `make interior` builds without a traceback, and the views you touched were rendered and checked.
- The docs still describe the code: update `docs/furniture.md` for new generators or parameters, and `docs/flat.md` for new measurements or confirmed heights.
- Don't commit renders: `renders/` is gitignored. The final images and plans are published as a GitHub release by the `Render` workflow (Actions tab, manual run).
