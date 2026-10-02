BLENDER ?= blender
SAMPLES ?= 256

.PHONY: all shell verify layout assets interior render preview evening tiles technical lint fmt test

all: shell layout assets interior render

shell:    ## Architectural shell from data/floorplan.json -> blender/apartment_shell.blend + plan renders
	$(BLENDER) --background --factory-startup --python-exit-code 1 --python scripts/build_shell.py

verify:   ## Overlay the shell plan render on the source PDF (renders/shell_overlay.png)
	uv run -q python scripts/verify_overlay.py

layout:   ## Furniture placeholder plan + clearance report (renders/layout_proposal.png)
	$(BLENDER) --background --factory-startup --python-exit-code 1 --python scripts/build_layout.py

assets:   ## Download CC0 assets from data/assets.json into assets/ (idempotent)
	python3 scripts/fetch_assets.py

interior: ## Furnished, lit scene -> blender/apartment.blend
	$(BLENDER) --background --factory-startup --python-exit-code 1 --python scripts/build_interior.py

CAMS ?= $(shell python3 -c "import json; print(' '.join(c for c in json.load(open('data/cameras.json'))['cameras'] if c != 'walk'))")

# One Blender process per view: HIP on the 8 GB card can fault after several renders in one process
render:   ## Final daylight views + furnished plan -> renders/interior/
	for c in $(CAMS); do $(BLENDER) -b blender/apartment.blend --python-exit-code 1 -P scripts/render.py -- --cams $$c --samples $(SAMPLES) || exit 1; done
	$(BLENDER) -b blender/apartment.blend --python-exit-code 1 -P scripts/render.py -- --cams none --samples $(SAMPLES) --plan

EVENING_CAMS ?= $(shell python3 scripts/ci_matrix.py --evening)
evening:  ## Evening views with lamps on
	for c in $(EVENING_CAMS); do $(BLENDER) -b blender/apartment.blend --python-exit-code 1 -P scripts/render.py -- --mode evening --cams $$c --samples $(SAMPLES) || exit 1; done

PREVIEW_CHUNK ?= 4
MODE ?= day
preview:  ## Fast half-size previews, PREVIEW_CHUNK views per process with persistent data (MODE=evening for lamps on) -> renders/preview/
	for g in $$(echo $(CAMS) | xargs -n $(PREVIEW_CHUNK) | tr ' ' ','); do $(BLENDER) -b blender/apartment.blend --python-exit-code 1 -P scripts/render.py -- --mode $(MODE) --cams $$g --samples 48 --scale 50 --out renders/preview || exit 1; done

tiles:    ## Debug: plot PDF vectors on a point grid, e.g. make tiles ARGS="t.png,335,600,170,300"
	uv run -q python scripts/plan_tiles.py $(ARGS)

technical: ## Dimensioned A3 technical plan, 3 sheets -> renders/technical_plan.pdf (+ PNGs)
	uv run -q python scripts/technical_plan.py

lint:     ## Ruff lint + format check
	uv run ruff check scripts tests
	uv run ruff format --check scripts tests

test:     ## Unit tests: data schemas, clearances, helpers (no Blender needed)
	uv run pytest -q

fmt:      ## Auto-fix lint issues and format
	uv run ruff check --fix scripts tests
	uv run ruff format scripts tests
	npx --yes prettier --write .