# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Cocolit counts coconut trees in a box the user draws on a satellite map. It is made of two FastAPI services, a website and a detector, plus PostGIS. It runs on a single k3s node behind a Cloudflare Tunnel, with Google Cloud Run as an overflow detector.

## Commands

```bash
uv sync --locked                                   # install, as CI does (Python 3.11)
uv run pytest tests --ignore=tests/integration -q  # unit tests, the same as CI
uv run pytest tests/test_tiles.py::test_name -q    # a single test
uv run pytest tests/integration -q                 # hits real tile servers (network)

# run locally, each in its own terminal (no database needed; results just aren't saved)
uv run uvicorn src.api.inference:app --port 8000                                    # detector
INFERENCE_URL=http://127.0.0.1:8000/predict uv run uvicorn main:app --port 8501     # website

uv run python -m scripts.benchmark_inference --sizes 0.1 1 2.5   # per-stage timings and peak RSS

# Helm checks run by CI
helm lint infra/charts/cocolit -f infra/charts/cocolit/values-laptop.yaml

scripts/deploy_laptop.sh        # build both images and helm upgrade on the local k3s (Colima)
scripts/deploy_cloud_run.sh     # build and deploy the overflow detector to Cloud Run
```

Docs use mkdocs-material: `mkdocs serve`, with requirements in `requirements_docs.txt`.

## Architecture

There are two separately deployed services. Each Dockerfile installs from its own requirements file, so dependencies must not leak between them:

- **Website**: `main.py` + `static/`.
  - Serves the Leaflet page (`static/index.html`, `static/js/app.js`).
  - Validates the bbox, then forwards it to the detector through `src/inference_router.InferenceRouter`, which tries local first and sends the request to Cloud Run (`INFERENCE_OVERFLOW_URL`) when local is busy or fails with 502/503/504/timeout. The backend that answered is returned in the `X-Inference-Backend` header.
  - Saves results to PostGIS through `src/dal` and `src/database`. Tables are created in the lifespan hook, and the DB is optional.
  - Requirements: `requirements_streamlit.txt` (a historical name; there is no Streamlit any more), which includes geopandas, sqlmodel and psycopg 3.
- **Detector**: `src/api/inference.py` → `pipelines/inference.py`. Requests need the `X-Api-Key` header when `INFERENCE_API_KEY` is set.
  - Requirements: `requirements_inference.txt`, which deliberately has **no geopandas, torch or ultralytics**, so the image stays around 111 MB. Anything imported on the detector path must stay within numpy, PIL, httpx and onnxruntime.
  - `src/utils/mercator.py` is pure math that both services share. `src/utils/tiles.py` pulls in httpx and PIL, so the website must not import it.
  - `src/data_struct/bbox.py` imports geopandas/shapely lazily for the same reason.

The detection pipeline (`pipelines/inference.py`) runs these stages: validate → detect → postprocess.

- `src/utils/tiles.py` plans a zoom-19 tile mosaic (`MosaicPlan`) and downloads tiles concurrently (`tile_workers`). `stream_patches` yields 640×640 patches row by row as tiles arrive, so inference overlaps with the download.
- `src/utils/detector.py` (`OnnxDetector`) runs `models/best.onnx`, a YOLO11n model with static input [1,3,640,640] and output [1,5,8400]. It does its own pre-processing, NMS and box clipping, and is meant to match ultralytics output exactly. Keep that parity when changing it.
- Points are georeferenced in EPSG:3857. `Predictions.to_geojson()` reproduces geopandas' GeoJSON format, including the `crs` member.
- An empty result must return an empty FeatureCollection, not an error.
- An oversized or undersized bbox (`BBoxTooBig`/`BBoxTooSmall`) maps to HTTP 422. The UI limit is 0.5 km².

Config lives in `configs/config.yml` (model path, tile workers, heatmap UI) plus environment variables listed in `.env.example`. The full environment table is in `docs/architecture.md`.

Frontend assets are cached at the Cloudflare edge. `index.html` references `?v=__ASSET_VERSION__`, which `frontend.Dockerfile` replaces with the `ASSET_VERSION` build arg. Keep that pattern when adding JS/CSS.

## Deployment

- The Helm chart lives in `infra/charts/cocolit`:
  - `values.yaml` is the default.
  - `values-laptop.yaml` is the current laptop k3s node, with local `:dev` images and `pullPolicy: Never`.
  - Secrets go in a gitignored `secrets-*.yaml`.
  - The chart includes CloudNativePG PostGIS and an optional `cloudflared`, which reads its token from the k8s secret `cloudflared-token`.
- The target is an Oracle Always Free A1 node (arm64), set up with OpenTofu in `infra/oci/`. `infra/tofu` is the old AWS setup, kept until teardown.
- CI (`.github/workflows/ci_cd.yml`) tests, lints the chart and pushes multi-arch (amd64 + arm64) images to `ghcr.io/davnish/{streamlit-server,inference-server}` with `GITHUB_TOKEN`. It does not deploy, because the cluster is only reachable through the tunnel.
- Docs are published from `main` (`docs_ci.yml`).

## Conventions

- Never add Claude `Co-Authored-By` or other attribution trailers to commits or PRs.
- Never write tokens or secrets to tracked files. They go in k8s secrets, `.env` or `secrets-*.yaml`.
- Licensing: the code is MIT, but `models/` (the YOLO11n weights) is AGPL-3.0. See `models/README.md`.
- In UI copy, say "coconut trees", not "palms".
