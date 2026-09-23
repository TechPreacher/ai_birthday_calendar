# syntax=docker/dockerfile:1

# ---- Builder: resolve and install dependencies into a venv ----
FROM python:3.12-slim AS builder

# uv for fast, reproducible installs (pinned by tag for repeatable builds)
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies only, from the lockfile, so this layer caches independently
# of the application source. The project itself is never pip-installed: it
# runs from source at /app, the same way the old systemd unit ran it out of
# /opt/birthdays.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ---- Runtime ----
FROM python:3.12-slim AS runtime

# uid 1000 matches the host account that owns ./data, so the bind-mounted
# JSON files stay writable by the container and readable/backup-able by you.
RUN useradd --system --uid 1000 --create-home --home-dir /home/birthdays birthdays

# Create the data directory in the image, owned by the service user. With a
# bind mount this is just the mount point, but if a Docker *named volume* is
# used instead, Docker seeds the new volume from this path -- including its
# ownership. Without it the volume is created root:root 0755 and the app,
# running as uid 1000, cannot write to it at all.
RUN mkdir -p /data && chown birthdays:birthdays /data

WORKDIR /app

COPY --from=builder --chown=birthdays:birthdays /app/.venv /app/.venv
COPY --chown=birthdays:birthdays app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BIRTHDAYS_DATA_DIR=/data

USER birthdays
EXPOSE 8081

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
