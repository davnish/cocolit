# Inference service: pure-wheel Python deps, no compilers or GDAL needed.
# Builds for linux/arm64 (Oracle A1, Apple Silicon) and linux/amd64 (Cloud Run).
FROM ghcr.io/astral-sh/uv:0.9-python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv

COPY requirements_inference.txt /tmp/
RUN uv venv $VIRTUAL_ENV && \
    uv pip install --no-cache --python $VIRTUAL_ENV/bin/python -r /tmp/requirements_inference.txt && \
    # onnxruntime depends on sympy only for offline graph tools; ~80 MB unused at runtime.
    uv pip uninstall --python $VIRTUAL_ENV/bin/python sympy mpmath

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="inference-server"
LABEL org.opencontainers.image.description="cocolit coconut-tree detection API"
LABEL org.opencontainers.image.source="https://github.com/davnish/cocolit"
# Code is MIT; the bundled models/best.onnx (YOLO11n, Ultralytics) is AGPL-3.0.
LABEL org.opencontainers.image.licenses="MIT AND AGPL-3.0"

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY configs ./configs
COPY src/__init__.py ./src/__init__.py
COPY src/api ./src/api
COPY src/data_struct/__init__.py src/data_struct/bbox.py ./src/data_struct/
COPY src/exceptions ./src/exceptions
COPY src/utils/__init__.py src/utils/mercator.py src/utils/tiles.py src/utils/detector.py ./src/utils/
COPY src/telemetry.py ./src/telemetry.py
COPY pipelines/__init__.py pipelines/inference.py ./pipelines/
COPY models/best.onnx ./models/best.onnx
RUN mkdir logs && chown app logs
USER 10001

EXPOSE 8000
# Cloud Run sets $PORT; k8s uses the default 8000.
CMD ["sh", "-c", "exec uvicorn src.api.inference:app --host 0.0.0.0 --port ${PORT} --no-access-log"]
