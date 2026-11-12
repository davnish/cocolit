# Frontend: FastAPI serving the map UI and talking to PostGIS + inference.
# Pure-wheel deps only (no GDAL/compilers), so it builds for arm64 and amd64 alike.
FROM ghcr.io/astral-sh/uv:0.9-python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv

COPY requirements_streamlit.txt /tmp/
RUN uv venv $VIRTUAL_ENV && \
    uv pip install --no-cache --python $VIRTUAL_ENV/bin/python -r /tmp/requirements_streamlit.txt

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="frontend"
LABEL org.opencontainers.image.description="cocolit web frontend"
LABEL org.opencontainers.image.source="https://github.com/davnish/cocolit"
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY configs ./configs
COPY src/__init__.py src/inference_router.py ./src/
COPY src/dal ./src/dal
COPY src/database ./src/database
COPY src/exceptions ./src/exceptions
COPY src/data_struct/__init__.py src/data_struct/bbox.py ./src/data_struct/
COPY src/utils/__init__.py src/utils/mercator.py ./src/utils/
COPY src/telemetry.py ./src/telemetry.py
COPY main.py ./main.py
COPY static ./static
# Cache-bust JS/CSS (Cloudflare caches them for hours; the HTML itself is not cached).
ARG ASSET_VERSION=dev
RUN sed -i "s/__ASSET_VERSION__/${ASSET_VERSION}/g" static/index.html
COPY data/countries ./data/countries
RUN mkdir logs && chown app logs
USER 10001

EXPOSE 8501
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8501", "--no-access-log"]
