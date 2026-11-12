import threading
from types import SimpleNamespace

import pytest
import requests

from src.inference_router import InferenceRouter

OK = {"status": "success", "predictions": {"type": "FeatureCollection", "features": []}}


def reply(status=200, body=OK):
    def raise_for_status():
        if status >= 400:
            raise requests.HTTPError(response=SimpleNamespace(status_code=status))
    return SimpleNamespace(json=lambda: body, raise_for_status=raise_for_status)


def test_local_first_when_idle(mocker):
    post = mocker.patch("src.inference_router.requests.post", return_value=reply())
    router = InferenceRouter("http://local/predict", "https://run.app/predict", api_key="k")

    assert router.predict({"xmin": 1})[1] == "local"
    url = post.call_args.args[0]
    assert url == "http://local/predict"
    assert post.call_args.kwargs["headers"] == {"X-Api-Key": "k"}
    assert router.inflight == 0


def test_overflow_when_local_is_busy(mocker):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        if url.startswith("http://local"):
            entered.set()
            release.wait(5)
        return reply()

    mocker.patch("src.inference_router.requests.post", side_effect=post)
    router = InferenceRouter("http://local/predict", "https://run.app/predict", max_local=1)

    first = threading.Thread(target=router.predict, args=({},))
    first.start()
    entered.wait(5)
    assert router.predict({})[1] == "overflow"
    release.set()
    first.join()
    assert calls == ["http://local/predict", "https://run.app/predict"]


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("refused"),
    requests.Timeout("slow"),
])
def test_overflow_when_local_is_down(mocker, failure):
    def post(url, **kwargs):
        if url.startswith("http://local"):
            raise failure
        return reply()

    mocker.patch("src.inference_router.requests.post", side_effect=post)
    router = InferenceRouter("http://local/predict", "https://run.app/predict")

    assert router.predict({})[1] == "overflow"
    assert router.inflight == 0


def test_overflow_on_503_but_not_on_bad_request(mocker):
    mocker.patch("src.inference_router.requests.post", side_effect=lambda url, **k: (
        reply(503) if url.startswith("http://local") else reply()))
    router = InferenceRouter("http://local/predict", "https://run.app/predict")
    assert router.predict({})[1] == "overflow"

    post = mocker.patch("src.inference_router.requests.post", return_value=reply(422))
    with pytest.raises(requests.HTTPError):
        router.predict({})
    assert post.call_count == 1  # a bad bbox is not retried on Cloud Run


def test_without_overflow_everything_goes_local(mocker):
    mocker.patch("src.inference_router.requests.post", side_effect=requests.ConnectionError("down"))
    router = InferenceRouter("http://local/predict", max_local=1)
    router._inflight = 5  # busy, but there is nowhere else to go

    with pytest.raises(requests.ConnectionError):
        router.predict({})


def test_inference_api_requires_key_when_configured(mocker):
    from fastapi.testclient import TestClient

    import src.api.inference as api

    mocker.patch.object(api, "API_KEY", "secret")
    client = TestClient(api.app)
    box = {"xmin": 80.0194, "ymin": 7.8084, "xmax": 80.0224, "ymax": 7.8112}

    assert client.post("/predict", json=box).status_code == 401
    assert client.post("/predict", json=box, headers={"X-Api-Key": "nope"}).status_code == 401
    assert client.get("/health").status_code == 200


def test_inference_api_rejects_oversized_box_with_422():
    from fastapi.testclient import TestClient

    import src.api.inference as api

    response = TestClient(api.app).post("/predict", json={"xmin": 79, "ymin": 7, "xmax": 80, "ymax": 8})
    assert response.status_code == 422
