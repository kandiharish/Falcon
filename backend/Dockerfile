# FALCON backend image: the same image runs the API, the processing worker and migrations.
#   docker build -t falcon-backend ./backend
FROM python:3.12-slim-bookworm

# OpenCV (used by RapidOCR) needs these two system libraries even without a screen.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv installs exactly the versions in uv.lock (reproducible builds).
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /app
# Dependencies first: this layer is cached until pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Never run as root: a compromised process would otherwise own the container.
RUN useradd --create-home --uid 10001 falcon \
    && mkdir -p /data/storage && chown -R falcon:falcon /data /app
USER falcon
ENV ENVIRONMENT=production STORAGE_DIR=/data/storage

EXPOSE 8000
# --proxy-headers: trust the client address that Caddy forwards (for audit logs and limits).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
