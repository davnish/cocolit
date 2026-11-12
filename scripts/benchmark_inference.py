"""Measure how long each inference pipeline stage takes, for several bbox sizes.

Runs the real pipeline (downloads satellite tiles, patches, runs the ONNX model)
in-process, so the numbers reflect this machine's CPU and network.

    python -m scripts.benchmark_inference                       # default sizes
    python -m scripts.benchmark_inference --sizes 0.1 1 --repeats 2
    python -m scripts.benchmark_inference --profile run         # cProfile whole runs
    python -m scripts.benchmark_inference --json results.json

Sizes are areas in km². The API rejects boxes over 5 km² (measured in EPSG:3857).
"""

import argparse
import cProfile
import io
import json
import math
import pstats
import threading
import time
from pathlib import Path

import numpy as np
import psutil
import yaml

# detect = download and model overlapped; tile_wait/model split it.
STAGES = ["validate", "detect", "tile_wait", "model", "postprocess"]
MODEL_SPLIT: list[str] = []
TILE_ZOOM = 19  # must match MosaicPlan.for_bounds() default in src/utils/tiles.py


class PeakRSS:
    """Samples this process's resident memory in a background thread."""

    def __init__(self, interval: float = 0.05) -> None:
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        self._proc = psutil.Process()

    def __enter__(self) -> "PeakRSS":
        self.peak = self._proc.memory_info().rss
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def _sample(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self._proc.memory_info().rss)
            time.sleep(self.interval)

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()


def square_bounds(lat: float, lon: float, area_km2: float) -> list[float]:
    """[xmin, ymin, xmax, ymax] in degrees for a ground square centred on lat/lon."""
    half = math.sqrt(area_km2 * 1e6) / 2
    dlat = half / 111_320
    dlon = half / (111_320 * math.cos(math.radians(lat)))
    return [lon - dlon, lat - dlat, lon + dlon, lat + dlat]


def tile_count(bounds: list[float], zoom: int = TILE_ZOOM) -> int:
    def deg2num(lat: float, lon: float) -> tuple[float, float]:
        lat_r = math.radians(lat)
        n = 2**zoom
        x = (lon + 180) / 360 * n
        y = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n
        return x, y

    xmin, ymin, xmax, ymax = bounds
    x0, y1 = deg2num(ymin, xmin)
    x1, y0 = deg2num(ymax, xmax)
    return (math.ceil(x1) - math.floor(x0)) * (math.ceil(y1) - math.floor(y0))


def profiled_stage(pipeline, stage: str) -> cProfile.Profile:
    """Wrap the pipeline so every run is cProfiled (download and model overlap now)."""
    profiler = cProfile.Profile()
    original = pipeline.run
    pipeline.run = lambda *a, **k: profiler.runcall(original, *a, **k)
    return profiler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=float, nargs="+", default=[0.1, 0.5, 1.0, 2.5])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument(
        "--center",
        type=float,
        nargs=2,
        metavar=("LAT", "LON"),
        default=[7.8098, 80.0209],  # coconut estate used in tests/integration
    )
    parser.add_argument("--profile", choices=["run"])
    parser.add_argument("--json", type=Path, help="write raw results to this file")
    args = parser.parse_args()

    from pipelines.inference import InferencePipeline
    from src.data_struct.bbox import BBox, BBoxBounds

    config = yaml.safe_load(Path("configs/config.yml").read_text())

    t0 = time.perf_counter()
    pipeline = InferencePipeline(config["model"]["path"])
    load_s = time.perf_counter() - t0
    # First predict builds the ONNX session; keep it out of the per-run numbers.
    t0 = time.perf_counter()
    pipeline.model(np.zeros((640, 640, 3), dtype=np.uint8))
    warmup_s = time.perf_counter() - t0
    print(f"model load {load_s:.2f}s, first-predict warmup {warmup_s:.2f}s\n")

    profiler = profiled_stage(pipeline, args.profile) if args.profile else None

    results = []
    for area_km2 in args.sizes:
        for rep in range(args.repeats):
            bounds = square_bounds(*args.center, area_km2)
            bbox = BBox(BBoxBounds(xmin=bounds[0], ymin=bounds[1], xmax=bounds[2], ymax=bounds[3]))

            with PeakRSS() as mem:
                t0 = time.perf_counter()
                pipeline.run(bbox)
                total = time.perf_counter() - t0

            # Mirrors src/api/inference.py building the response body.
            t0 = time.perf_counter()
            body = bbox.preds.to_geojson()
            serialize_s = time.perf_counter() - t0

            row = {
                "area_km2": area_km2,
                "repeat": rep,
                "tiles": tile_count(bounds),
                "detections": len(bbox.preds),
                "total_s": total,
                "serialize_s": serialize_s,
                "peak_rss_mb": mem.peak / 2**20,
                "response_kb": len(json.dumps(body)) / 1024,
                **bbox.timings,
            }
            results.append(row)
            print(
                f"{area_km2:>5} km²  total {total:6.2f}s  "
                + "  ".join(f"{s} {row.get(s, 0):.2f}" for s in STAGES)
            )

    print_table(results)

    if profiler:
        out = io.StringIO()
        pstats.Stats(profiler, stream=out).sort_stats("cumulative").print_stats(25)
        print(f"\n=== cProfile: {args.profile} (all runs, cumulative) ===")
        print(out.getvalue())

    if args.json:
        args.json.write_text(json.dumps(results, indent=2))
        print(f"wrote {args.json}")


def print_table(results: list[dict]) -> None:
    cols = (
        ["area_km2", "tiles", "detections"]
        + STAGES
        + MODEL_SPLIT
        + ["serialize_s", "total_s", "peak_rss_mb", "response_kb"]
    )
    print()
    print(" | ".join(f"{c:>17}" for c in cols))
    for r in results:
        cells = []
        for c in cols:
            v = r.get(c, 0)
            cells.append(f"{v:>17.2f}" if isinstance(v, float) else f"{v:>17}")
        print(" | ".join(cells))
    print("\nshare of total time (mean across runs):")
    for s in STAGES + ["serialize_s"]:
        share = np.mean([r.get(s, 0) / r["total_s"] for r in results]) * 100
        print(f"  {s:<12} {share:5.1f}%")


if __name__ == "__main__":
    main()
