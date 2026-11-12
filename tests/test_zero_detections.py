"""Regression tests: an area with no trees must return an empty result, not a 500."""

import os
from types import SimpleNamespace

from fastapi.testclient import TestClient

from pipelines.inference import empty_predictions

BOX = {"xmin": 80.0194, "ymin": 7.8084, "xmax": 80.0224, "ymax": 7.8112}


def test_inference_api_returns_empty_feature_collection(mocker):
    import src.api.inference as api

    def run(bbox):
        bbox.preds = empty_predictions()
        return bbox

    mocker.patch.object(api.inference, "run", side_effect=run)

    response = TestClient(api.app).post("/predict", json=BOX)

    assert response.status_code == 200
    assert response.json()["predictions"]["features"] == []


def test_frontend_returns_empty_features(mocker):
    import main

    upstream = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "status": "success",
            "predictions": {"type": "FeatureCollection", "features": []},
        },
    )
    post = mocker.patch("src.inference_router.requests.post", return_value=upstream)
    mocker.patch.dict(os.environ, {"INFERENCE_URL": "http://inference/predict"})
    mocker.patch("main._router", None)
    mocker.patch("main.engine", None)  # skip the database write

    response = TestClient(main.app).post("/api/inference", json={
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [BOX["xmin"], BOX["ymin"]], [BOX["xmax"], BOX["ymin"]],
                [BOX["xmax"], BOX["ymax"]], [BOX["xmin"], BOX["ymax"]],
                [BOX["xmin"], BOX["ymin"]],
            ]],
        },
    })

    assert response.status_code == 200
    assert response.json() == {"features": []}
    assert response.headers["X-Inference-Backend"] == "local"
    post.assert_called_once()
