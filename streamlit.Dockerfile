# Stage 1: Build and Install Dependencies
FROM ghcr.io/astral-sh/uv:0.5-python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv

WORKDIR /app

# We need libgdal-dev here to provide headers for the wheel build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=requirements_streamlit.txt,target=requirements_streamlit.txt \
    uv venv $VIRTUAL_ENV && \
    uv pip install -r requirements_streamlit.txt

# --- Stage 2: Final Runtime Image ---
FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/davnish/cocolit"

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# INSTALL ONLY RUNTIME BINARIES HERE
# libgdal32 is the runtime library that provides libgdal.so.32
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv and source code
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY pipelines ./pipelines
COPY configs ./configs
COPY main.py ./main.py

EXPOSE 8501

CMD [ "streamlit", "run", "main.py" ]