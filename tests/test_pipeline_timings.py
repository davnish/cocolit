import numpy as np
import pytest

import pipelines.inference as inference_mod
from pipelines.inference import InferencePipeline
from src.data_struct.bbox import BBox, BBoxBounds
from src.exceptions.exceptions import BBoxTooBig
from src.utils.detector import Detections
from src.utils.tiles import GeoImage, iter_patches

# 0.1 km²-ish box; the area only matters for validation.
BOUNDS = BBoxBounds(xmin=80.0194, ymin=7.8084, xmax=80.0224, ymax=7.8112)


def boxes(xywh_px, conf):
    xywh = np.asarray(xywh_px, dtype=float).reshape(-1, 4)
    return Detections(xywh, np.asarray(conf, dtype=float), np.zeros(len(conf), int))


NONE = boxes([], [])


def make_pipeline(results):
    """Pipeline with a fake model returning `results` one per patch, in order."""
    pipeline = InferencePipeline.__new__(InferencePipeline)  # skip loading model/client
    pipeline.tile_workers = 4
    pipeline.client = None
    queue = list(results)

    def model(array):
        assert array.shape == (640, 640, 3)
        return queue.pop(0)

    pipeline.model = model
    return pipeline


def fake_image(height=700, width=700):
    # 2x2 patch grid; 1 m pixels; top-left corner at (1000, 5000) in EPSG:3857
    return GeoImage(
        array=np.zeros((height, width, 3), np.uint8),
        left=1000.0, top=5000.0, pixel_width=1.0, pixel_height=1.0,
    )


def use_image(mocker, image):
    """Serve `image` through the streaming download, georeferenced like a real plan."""
    plan = mocker.Mock(
        height=image.array.shape[0], width=image.array.shape[1], tile_count=4,
        pixel_width=image.pixel_width, pixel_height=image.pixel_height,
    )
    mocker.patch.object(inference_mod.MosaicPlan, "for_bounds", return_value=plan)
    return mocker.patch.object(
        inference_mod, "stream_patches", side_effect=lambda *a, **k: iter_patches(image, 640)
    )


def test_run_converts_boxes_to_3857_points_and_times_stages(mocker):
    use_image(mocker, fake_image())
    results = [
        boxes([[320, 160, 64, 64]], [0.9]),  # patch (0, 0)
        NONE,                                # patch (0, 1)
        NONE,                                # patch (1, 0)
        boxes([[0, 640, 64, 64]], [0.4]),    # patch (1, 1)
    ]
    bbox = BBox(BOUNDS)

    make_pipeline(results).run(bbox)

    assert list(bbox.preds.conf) == pytest.approx([0.9, 0.4])
    points = list(zip(bbox.preds.x, bbox.preds.y))
    # patch (0,0): x = 1000 + 0.5*640, y = 5000 - 0.25*640
    # patch (1,1): left = 1000 + 640, top = 5000 - 640; x = left + 0, y = top - 640
    assert [c for pt in points for c in pt] == pytest.approx([1320.0, 4840.0, 1640.0, 3720.0])

    for stage in ["validate", "detect", "postprocess", "tile_wait", "model"]:
        assert bbox.timings[stage] >= 0


def test_no_detections_returns_empty_geodataframe(mocker):
    use_image(mocker, fake_image(600, 600))
    bbox = BBox(BOUNDS)

    make_pipeline([NONE]).run(bbox)

    assert len(bbox.preds) == 0
    assert bbox.preds.to_geojson()["features"] == []


def test_invalid_bbox_is_timed_and_raised(mocker):
    fetch = mocker.patch.object(inference_mod, "stream_patches")
    bbox = BBox(BBoxBounds(xmin=79.0, ymin=7.0, xmax=80.0, ymax=8.0))  # far over 5 km²

    with pytest.raises(BBoxTooBig):
        make_pipeline([]).run(bbox)

    assert "validate" in bbox.timings
    fetch.assert_not_called()


def test_geojson_matches_geopandas_to_json():
    import json

    import geopandas as gpd

    preds = inference_mod.Predictions(np.array([1.5, 3.0]), np.array([2.0, -4.25]), np.array([0.9, 0.3]))
    gdf = gpd.GeoDataFrame(
        {"conf": preds.conf}, geometry=gpd.points_from_xy(preds.x, preds.y), crs="EPSG:3857"
    )

    assert preds.to_geojson() == json.loads(gdf.to_json())
