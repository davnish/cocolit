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

LABEL org.opencontainers.image.title="streamlit-frontend"
LABEL org.opencontainers.image.description="Streamlit frontend"
LABEL org.opencontainers.image.source="https://github.com/davnish/cocolit"
LABEL org.opencontainers.image.licenses="MIT"


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
COPY static ./static
COPY misc ./misc
COPY data ./data

EXPOSE 8501

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8501"]