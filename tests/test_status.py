import base64

import pytest

from src import status


def _b64(hex_id: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_id)).decode()


def _span(name, span_id, parent, start_ms, end_ms, attributes=None):
    return {
        "name": name,
        "spanId": _b64(span_id),
        "parentSpanId": _b64(parent) if parent else None,
        "kind": "SPAN_KIND_INTERNAL",
        "startTimeUnixNano": str(1_000_000_000 + start_ms * 1_000_000),
        "endTimeUnixNano": str(1_000_000_000 + end_ms * 1_000_000),
        "attributes": attributes or [],
    }


def _batch(service, spans):
    return {
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]},
        "scopeSpans": [{"spans": spans}],
    }


TRACE = {
    "batches": [
        _batch("cocolit-inference", [
            _span("inference.detect", "04", "03", 12, 90),
            _span("inference.pipeline", "03", "02", 10, 95, [
                {"key": "cocolit.detections", "value": {"intValue": "42"}},
                {"key": "cocolit.bbox.area_m2", "value": {"doubleValue": 1500.5}},
                {"key": "cocolit.secret", "value": {"stringValue": "not for the page"}},
            ]),
            _span("POST /predict", "02", "01", 5, 98),
            _span("POST /predict http send", "05", "02", 97, 98),
        ]),
        _batch("cocolit-frontend", [
            _span("POST /api/inference", "01", None, 0, 100, [
                {"key": "http.url", "value": {"stringValue": "https://example/?lat=1"}},
            ]),
        ]),
    ]
}


def test_simplify_trace_orders_by_parent_and_drops_asgi_spans():
    out = status.simplify_trace(TRACE)
    assert [(s["name"], s["depth"]) for s in out["spans"]] == [
        ("POST /api/inference", 0),
        ("POST /predict", 1),
        ("inference.pipeline", 2),
        ("inference.detect", 3),
    ]
    assert out["duration_ms"] == 100
    assert out["spans"][3]["start_ms"] == 12
    assert out["spans"][3]["duration_ms"] == 78
    assert out["spans"][1]["service"] == "cocolit-inference"


def test_simplify_trace_exposes_only_whitelisted_numbers():
    out = status.simplify_trace(TRACE)
    assert out["detections"] == 42
    assert out["area_m2"] == 1500.5
    assert "not for the page" not in str(out)
    assert "example" not in str(out)
    assert set(out["spans"][0]) == {"service", "name", "kind", "depth", "start_ms", "duration_ms"}


def test_simplify_trace_empty():
    assert status.simplify_trace({"batches": []}) is None


def test_pods_are_grouped_by_role_and_unknown_pods_dropped():
    rows = status._pods({
        "pod_cpu_cores": {"cocolit-streamlit-deployment-abc": 0.1, "cocolit-inference-server-x": 0.5, "mystery": 9},
        "pod_memory_bytes": {"cocolit-streamlit-deployment-abc": 100.0, "cocolit-postgis-1": 50.0},
        "pod_memory_limit_bytes": {"cocolit-streamlit-deployment-abc": 400.0},
    })
    assert [r["name"] for r in rows] == ["Website", "Detector", "PostGIS database"]
    assert rows[0] == {"name": "Website", "cpu_cores": 0.1, "memory_bytes": 100.0, "memory_limit_bytes": 400.0}
    assert rows[1]["memory_limit_bytes"] is None


@pytest.mark.parametrize("value,expected", [("1.5", 1.5), ("NaN", None), ("+Inf", None), (None, None)])
def test_finite(value, expected):
    assert status._finite(value) == expected


def test_unavailable_without_configuration(monkeypatch):
    monkeypatch.delenv("MONITORING_PROMETHEUS_URL", raising=False)
    assert status.get_status() == {"available": False}


def test_unavailable_when_monitoring_is_down(monkeypatch):
    monkeypatch.setenv("MONITORING_PROMETHEUS_URL", "http://prometheus.invalid")
    monkeypatch.setattr(status, "_cache", {"at": 0.0, "value": None})

    def boom(*args, **kwargs):
        raise status.requests.ConnectionError("down")

    monkeypatch.setattr(status.requests, "get", boom)
    assert status.get_status() == {"available": False}
