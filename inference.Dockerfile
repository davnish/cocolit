# Stage 1: Build and Install Dependencies
FROM ghcr.io/astral-sh/uv:0.5-python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Install system dependencies + GDAL headers
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=bind,source=packages.txt,target=packages.txt \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    $(grep -vE '^\s*#|^\s*$' /app/packages.txt) \
    && rm -rf /var/lib/apt/lists/*

# Install build-time Python deps first, then the rest
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=requirements_inference.txt,target=requirements_inference.txt \
    uv venv $VIRTUAL_ENV && \
    uv pip install cython setuptools wheel numpy && \
    uv pip install -r requirements_inference.txt

# Stage 2: Final Runtime Image
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="inference-server"
LABEL org.opencontainers.image.description="inference-server"
LABEL org.opencontainers.image.source="https://github.com/davnish/cocolit"
LABEL org.opencontainers.image.licenses="MIT"

# Install ONLY the runtime GDAL library (required for rasterio to run)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    CPLUS_INCLUDE_PATH=/usr/include/gdal \
    C_INCLUDE_PATH=/usr/include/gdal \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy the venv and source code
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY pipelines ./pipelines
COPY models ./models
COPY configs ./configs

EXPOSE 8000
CMD [ "uvicorn", "src.api.inference:app" , "--host", "0.0.0.0", "--port", "8000"]