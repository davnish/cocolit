from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Iterator

import httpx
import numpy as np
from opentelemetry import metrics, trace

from configs.logger import setup_logger
from src.data_struct.bbox import BBox
from src.utils.detector import OnnxDetector
from src.utils.tiles import MosaicPlan, stream_patches

logger = setup_logger("inference", "inference.log")

PATCH_SIZE = 640

# No-ops until src.telemetry.setup_telemetry() installs real providers.
tracer = trace.get_tracer("cocolit.inference")
meter = metrics.get_meter("cocolit.inference")

STAGE_DURATION = meter.create_histogram(
    "cocolit.inference.stage.duration",
    unit="s",
    description="Wall time of each inference pipeline stage",
    explicit_bucket_boundaries_advisory=[
        0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120,
    ],
)
BBOX_AREA = meter.create_histogram(
    "cocolit.inference.bbox.area",
    unit="m2",
    description="Area of each requested bounding box",
    explicit_bucket_boundaries_advisory=[
        625, 1e4, 5e4, 1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6,
    ],
)
PATCHES = meter.create_histogram(
    "cocolit.inference.patches",
    unit="{patch}",
    description="Number of 640px patches the model ran on per request",
    explicit_bucket_boundaries_advisory=[1, 2, 4, 8, 16, 32, 64, 128, 256],
)
DETECTIONS = meter.create_histogram(
    "cocolit.inference.detections",
    unit="{detection}",
    description="Trees detected per request",
    explicit_bucket_boundaries_advisory=[0, 10, 50, 100, 250, 500, 1000, 2500, 5000],
)
CONFIDENCE = meter.create_histogram(
    "cocolit.inference.detection.confidence",
    description="Confidence of each detection; a shift over time hints at drift",
    explicit_bucket_boundaries_advisory=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
)


@dataclass
class Predictions:
    """Detected tree centres in EPSG:3857 metres."""

    x: np.ndarray
    y: np.ndarray
    conf: np.ndarray

    def __len__(self) -> int:
        return len(self.conf)

    def to_geojson(self) -> dict:
        """FeatureCollection in the same shape geopandas' to_json() produced."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "id": str(i),
                    "type": "Feature",
                    "properties": {"conf": c},
                    "geometry": {"type": "Point", "coordinates": [x, y]},
                }
                for i, (x, y, c) in enumerate(
                    zip(self.x.tolist(), self.y.tolist(), self.conf.tolist())
                )
            ],
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3857"}},
        }


def empty_predictions() -> Predictions:
    return Predictions(np.empty(0), np.empty(0), np.empty(0))


def collect_predictions(xs: list, ys: list, confs: list) -> Predictions:
    if not xs:
        return empty_predictions()
    return Predictions(
        np.concatenate(xs).astype(float),
        np.concatenate(ys).astype(float),
        np.concatenate(confs).astype(float),
    )


class InferencePipeline:
    def __init__(self, model_path: str, tile_workers: int = 16) -> None:
        self.model = OnnxDetector(model_path)
        self.tile_workers = tile_workers
        # Shared across requests for connection reuse; httpx.Client is thread-safe.
        limits = httpx.Limits(
            max_connections=tile_workers, max_keepalive_connections=tile_workers
        )
        self.client = httpx.Client(limits=limits, timeout=60)

    @contextmanager
    def _stage(self, name: str, timings: dict) -> Iterator[trace.Span]:
        """Time one stage: child span + duration histogram + timings[name]."""
        outcome = "ok"
        start = perf_counter()
        with tracer.start_as_current_span(f"inference.{name}") as span:
            try:
                yield span
            except BaseException:
                outcome = "error"
                raise
            finally:
                elapsed = perf_counter() - start
                timings[name] = elapsed
                STAGE_DURATION.record(elapsed, {"stage": name, "outcome": outcome})
                logger.info(f"stage={name} outcome={outcome} seconds={elapsed:.3f}")

    def run(self, bbox: BBox) -> BBox:
        """Fill bbox.preds with detections (EPSG:3857 points, possibly empty)."""
        bbox.timings = {}
        timings = bbox.timings
        with tracer.start_as_current_span("inference.pipeline") as span:
            span.set_attribute("cocolit.bbox.area_m2", float(bbox.area))

            with self._stage("validate", timings):
                bbox.valid_bbox()
            BBOX_AREA.record(float(bbox.area))

            plan = MosaicPlan.for_bounds(bbox.bounds)
            rows = -(-plan.height // PATCH_SIZE)
            cols = -(-plan.width // PATCH_SIZE)
            n_patches = rows * cols
            PATCHES.record(n_patches)
            span.set_attribute("cocolit.patches", n_patches)
            span.set_attribute("cocolit.tiles", plan.tile_count)

            # Download and model overlap: each patch row is predicted as soon as its
            # tiles arrive. tile_wait = time the model sat idle waiting for tiles.
            xs, ys, confs = [], [], []
            tile_wait = model_time = 0.0
            with self._stage("detect", timings):
                patches = stream_patches(
                    plan, self.client, PATCH_SIZE, workers=self.tile_workers
                )
                while True:
                    t0 = perf_counter()
                    patch = next(patches, None)
                    t1 = perf_counter()
                    tile_wait += t1 - t0
                    if patch is None:
                        break
                    found = self.model(patch.array)
                    model_time += perf_counter() - t1
                    if not len(found.conf):
                        continue
                    # Box centres are patch pixels; map them to EPSG:3857 metres.
                    xs.append(patch.left + found.xywh[:, 0] * plan.pixel_width)
                    ys.append(patch.top - found.xywh[:, 1] * plan.pixel_height)
                    confs.append(found.conf)
            timings["tile_wait"] = tile_wait
            timings["model"] = model_time

            with self._stage("postprocess", timings):
                bbox.preds = collect_predictions(xs, ys, confs)

            n_detections = len(bbox.preds)
            DETECTIONS.record(n_detections)
            span.set_attribute("cocolit.detections", n_detections)
            for conf in bbox.preds.conf.tolist():
                CONFIDENCE.record(float(conf))
            return bbox
