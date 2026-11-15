"""Live server numbers for the public page (`/api/status`).

Reads a fixed set of queries from Prometheus and the latest detection trace
from Tempo on the monitoring node, and returns plain numbers. Visitors never
get query access: the queries are fixed here, and only durations, names and
resource figures leave this module (no span attributes such as coordinates).

Both URLs are optional. Without `MONITORING_PROMETHEUS_URL` the endpoint
answers `{"available": false}` and the page hides the section.

    MONITORING_PROMETHEUS_URL   e.g. http://10.0.1.81:30090
    MONITORING_TEMPO_URL        e.g. http://10.0.1.81:30093
"""

import base64
import contextlib
import os
import threading
import time

import requests

try:  # keep these calls out of the app's own traces
    from opentelemetry.instrumentation.utils import suppress_http_instrumentation
except ImportError:  # pragma: no cover
    suppress_http_instrumentation = contextlib.nullcontext

CLUSTER = 'cluster="cocolit-app"'
APP = f'{CLUSTER},namespace="apps"'
TIMEOUT = 4  # seconds per request to the monitoring node
CACHE_SECONDS = 30
WINDOW = "7d"  # for latency percentiles: a hobby site has quiet days
HISTORY_SECONDS = 3600
HISTORY_STEP = 120

# name -> PromQL returning one number
SCALARS = {
    "cpu_percent": f'100 * (1 - avg(rate(node_cpu_seconds_total{{{CLUSTER},mode="idle"}}[5m])))',
    "cpu_cores": f'count(count by (cpu)(node_cpu_seconds_total{{{CLUSTER},mode="idle"}}))',
    "memory_used_bytes": f"sum(node_memory_MemTotal_bytes{{{CLUSTER}}} - node_memory_MemAvailable_bytes{{{CLUSTER}}})",
    "memory_total_bytes": f"sum(node_memory_MemTotal_bytes{{{CLUSTER}}})",
    "disk_used_bytes": (
        f'sum(node_filesystem_size_bytes{{{CLUSTER},mountpoint="/"}}'
        f' - node_filesystem_avail_bytes{{{CLUSTER},mountpoint="/"}})'
    ),
    "disk_total_bytes": f'sum(node_filesystem_size_bytes{{{CLUSTER},mountpoint="/"}})',
    # Highest values seen over WINDOW, sampled every 5 minutes.
    "cpu_peak_percent": (
        f'max_over_time((100 * (1 - avg(rate(node_cpu_seconds_total{{{CLUSTER},mode="idle"}}[5m]))))[{WINDOW}:5m])'
    ),
    "memory_peak_bytes": (
        f"max_over_time(sum(node_memory_MemTotal_bytes{{{CLUSTER}}}"
        f" - node_memory_MemAvailable_bytes{{{CLUSTER}}})[{WINDOW}:5m])"
    ),
    "disk_peak_bytes": (
        f'max_over_time(sum(node_filesystem_size_bytes{{{CLUSTER},mountpoint="/"}}'
        f' - node_filesystem_avail_bytes{{{CLUSTER},mountpoint="/"}})[{WINDOW}:5m])'
    ),
    "request_p50_seconds": (
        "histogram_quantile(0.5, sum by (le)(rate(http_server_duration_milliseconds_bucket"
        f'{{{CLUSTER},job="cocolit-frontend",http_target="/api/inference"}}[{WINDOW}]))) / 1000'
    ),
    "request_p95_seconds": (
        "histogram_quantile(0.95, sum by (le)(rate(http_server_duration_milliseconds_bucket"
        f'{{{CLUSTER},job="cocolit-frontend",http_target="/api/inference"}}[{WINDOW}]))) / 1000'
    ),
    "detections": f"sum(increase(cocolit_inference_stage_duration_seconds_count{{{CLUSTER},stage=\"detect\"}}[{WINDOW}]))",
}

# name -> (PromQL returning one series per label value, label)
VECTORS = {
    "stage_p95_seconds": (
        "histogram_quantile(0.95, sum by (le, stage)"
        f"(rate(cocolit_inference_stage_duration_seconds_bucket{{{CLUSTER}}}[{WINDOW}])))",
        "stage",
    ),
    "pod_cpu_cores": (
        f'sum by (pod)(rate(container_cpu_usage_seconds_total{{{APP},container!=""}}[5m]))',
        "pod",
    ),
    "pod_memory_bytes": (
        f'sum by (pod)(container_memory_working_set_bytes{{{APP},container!=""}})',
        "pod",
    ),
    "pod_memory_limit_bytes": (
        f'sum by (pod)(kube_pod_container_resource_limits{{{APP},resource="memory"}})',
        "pod",
    ),
}

HISTORY = {
    "cpu_percent": SCALARS["cpu_percent"],
    "memory_percent": (
        f"100 * sum(node_memory_MemTotal_bytes{{{CLUSTER}}} - node_memory_MemAvailable_bytes{{{CLUSTER}}})"
        f" / sum(node_memory_MemTotal_bytes{{{CLUSTER}}})"
    ),
}

# Pod name prefix -> what a visitor would call it. First match wins.
POD_ROLES = (
    ("cocolit-streamlit", "Website"),
    ("cocolit-inference", "Detector"),
    ("cloudflared", "Cloudflare Tunnel"),
    ("cocolit-cloudflared", "Cloudflare Tunnel"),
    ("postgis", "PostGIS database"),
    ("cocolit-postgis", "PostGIS database"),
)

STAGE_ORDER = ("validate", "detect", "postprocess")
TRACE_QUERY = '{resource.service.name="cocolit-frontend" && name="POST /api/inference"}'
# ASGI bookkeeping spans ("... http send/receive") add nothing for a reader.
SKIP_SPAN_SUFFIXES = (" http send", " http receive")
PIPELINE_ATTRS = {
    "cocolit.bbox.area_m2": "area_m2",
    "cocolit.patches": "patches",
    "cocolit.tiles": "tiles",
    "cocolit.detections": "detections",
}

_cache: dict = {"at": 0.0, "value": None}
_lock = threading.Lock()


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _prom(base: str, path: str, **params) -> list:
    response = requests.get(f"{base}/api/v1/{path}", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["data"]["result"]


def _scalar(base: str, query: str) -> float | None:
    result = _prom(base, "query", query=query)
    return _finite(result[0]["value"][1]) if result else None


def _vector(base: str, query: str, label: str) -> dict[str, float]:
    out = {}
    for series in _prom(base, "query", query=query):
        value = _finite(series["value"][1])
        if value is not None:
            out[series["metric"].get(label, "")] = value
    return out


def _history(base: str, query: str, now: float) -> list[list[float]]:
    result = _prom(
        base, "query_range", query=query, start=now - HISTORY_SECONDS, end=now, step=HISTORY_STEP
    )
    if not result:
        return []
    return [[int(t), round(v, 1)] for t, raw in result[0]["values"] if (v := _finite(raw)) is not None]


def pod_role(pod: str) -> str | None:
    for prefix, role in POD_ROLES:
        if pod.startswith(prefix):
            return role
    return None


def _pods(vectors: dict) -> list[dict]:
    """One row per role (pods of a role summed), in POD_ROLES order."""
    rows: dict[str, dict] = {}
    for key, field in (
        ("pod_cpu_cores", "cpu_cores"),
        ("pod_memory_bytes", "memory_bytes"),
        ("pod_memory_limit_bytes", "memory_limit_bytes"),
    ):
        for pod, value in vectors.get(key, {}).items():
            role = pod_role(pod)
            if role is None:
                continue
            row = rows.setdefault(role, {"name": role, "cpu_cores": 0.0, "memory_bytes": 0.0, "memory_limit_bytes": None})
            row[field] = (row[field] or 0.0) + value
    order = list(dict.fromkeys(role for _, role in POD_ROLES))
    return [rows[role] for role in order if role in rows]


def _attr(attributes: list, key: str):
    for attribute in attributes or []:
        if attribute.get("key") == key:
            value = attribute.get("value", {})
            for kind in ("intValue", "doubleValue", "stringValue"):
                if kind in value:
                    return value[kind]
    return None


def _span_id(raw: str | None) -> str | None:
    """Tempo returns ids as base64 in JSON; normalise so parents match children."""
    if not raw:
        return None
    try:
        return base64.b64decode(raw).hex()
    except Exception:
        return raw


def simplify_trace(trace: dict) -> dict | None:
    """Tempo's OTLP JSON -> a flat, ordered span list safe to show publicly."""
    spans = []
    summary: dict = {}
    for batch in trace.get("batches", []):
        service = _attr(batch.get("resource", {}).get("attributes"), "service.name") or "unknown"
        for scope in batch.get("scopeSpans", []):
            for span in scope.get("spans", []):
                name = span.get("name", "")
                if name.endswith(SKIP_SPAN_SUFFIXES):
                    continue
                start = int(span["startTimeUnixNano"])
                end = int(span["endTimeUnixNano"])
                spans.append({
                    "id": _span_id(span.get("spanId")),
                    "parent": _span_id(span.get("parentSpanId")),
                    "service": service,
                    "name": name,
                    "kind": span.get("kind", ""),
                    "start": start,
                    "end": end,
                })
                if name == "inference.pipeline":
                    for key, field in PIPELINE_ATTRS.items():
                        value = _finite(_attr(span.get("attributes"), key))
                        if value is not None:
                            summary[field] = value
    if not spans:
        return None

    ids = {span["id"] for span in spans}
    children: dict = {}
    for span in spans:
        parent = span["parent"] if span["parent"] in ids else None
        children.setdefault(parent, []).append(span)
    origin = min(span["start"] for span in spans)
    ordered = []

    def walk(parent, depth):
        for span in sorted(children.get(parent, []), key=lambda s: s["start"]):
            ordered.append({
                "service": span["service"],
                "name": span["name"],
                "kind": span["kind"].replace("SPAN_KIND_", "").lower(),
                "depth": depth,
                "start_ms": round((span["start"] - origin) / 1e6, 2),
                "duration_ms": round((span["end"] - span["start"]) / 1e6, 2),
            })
            walk(span["id"], depth + 1)

    walk(None, 0)
    return {
        "started_at": origin / 1e9,
        "duration_ms": round((max(span["end"] for span in spans) - origin) / 1e6, 2),
        "spans": ordered,
        **summary,
    }


def _latest_trace(base: str, now: float) -> dict | None:
    search = requests.get(
        f"{base}/api/search",
        params={"q": TRACE_QUERY, "limit": 20, "start": int(now - 7 * 86400), "end": int(now)},
        timeout=TIMEOUT,
    )
    search.raise_for_status()
    traces = search.json().get("traces") or []
    if not traces:
        return None
    # Tempo does not promise newest-first, so pick the newest ourselves.
    latest = max(traces, key=lambda t: int(t.get("startTimeUnixNano", 0)))
    trace = requests.get(f"{base}/api/traces/{latest['traceID']}", timeout=TIMEOUT)
    trace.raise_for_status()
    return simplify_trace(trace.json())


def _collect(prometheus: str, tempo: str | None) -> dict:
    now = time.time()
    with suppress_http_instrumentation():
        node = {name: _scalar(prometheus, query) for name, query in SCALARS.items()}
        vectors = {name: _vector(prometheus, query, label) for name, (query, label) in VECTORS.items()}
        history = {name: _history(prometheus, query, now) for name, query in HISTORY.items()}
        trace = None
        if tempo:
            try:
                trace = _latest_trace(tempo, now)
            except (requests.RequestException, ValueError, KeyError):
                trace = None  # the rest of the panel is still worth showing

    stages = vectors["stage_p95_seconds"]
    return {
        "available": True,
        "updated_at": now,
        "window": WINDOW,
        "node": {
            "cpu_percent": node["cpu_percent"],
            "cpu_cores": node["cpu_cores"],
            "memory_used_bytes": node["memory_used_bytes"],
            "memory_total_bytes": node["memory_total_bytes"],
            "disk_used_bytes": node["disk_used_bytes"],
            "disk_total_bytes": node["disk_total_bytes"],
            "cpu_peak_percent": node["cpu_peak_percent"],
            "memory_peak_bytes": node["memory_peak_bytes"],
            "disk_peak_bytes": node["disk_peak_bytes"],
        },
        "history": history,
        "pods": _pods(vectors),
        "latency": {
            "detections": node["detections"],
            "request_p50_seconds": node["request_p50_seconds"],
            "request_p95_seconds": node["request_p95_seconds"],
            "stages": [
                {"stage": stage, "p95_seconds": stages[stage]} for stage in STAGE_ORDER if stage in stages
            ],
        },
        "trace": trace,
    }


def get_status() -> dict:
    """Cached for CACHE_SECONDS; never raises (monitoring is optional)."""
    prometheus = (os.environ.get("MONITORING_PROMETHEUS_URL") or "").rstrip("/")
    if not prometheus:
        return {"available": False}
    tempo = (os.environ.get("MONITORING_TEMPO_URL") or "").rstrip("/") or None
    with _lock:
        if _cache["value"] is not None and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["value"]
        try:
            value = _collect(prometheus, tempo)
        except (requests.RequestException, ValueError, KeyError, IndexError):
            value = {"available": False}
        _cache.update(at=time.time(), value=value)
        return value
