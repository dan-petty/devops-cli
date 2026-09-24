FROM debian:sid

# Avoid interactive prompts during apt operations in CI
ARG DEBIAN_FRONTEND=noninteractive

# Optimize Python runtime and uv execution in containerized environments
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install Python 3.14 runtime, symlinks, root certificates, and the gnome-keyring Secret Service
# (dbus-x11 satisfies its session-bus dependency without pulling in systemd) with BuildKit apt
# cache mounts. /run/user/1000 holds the container-local session bus; /tmp is shared.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.14 \
    python-is-python3 \
    ca-certificates \
    shellcheck \
    gnome-keyring \
    dbus-x11 \
    && install -d -m 0700 -o 1000 -g 1000 /run/user/1000 \
    && sed -i 's/VERSION_CODENAME=forky/VERSION_CODENAME=trixie/' /etc/os-release \
    && rm -rf /var/lib/apt/lists/*

# Install standalone uv and uvx binaries into /usr/local/bin pinned to release
COPY --from=ghcr.io/astral-sh/uv:0.12.16 /uv /uvx /usr/local/bin/

# Pre-install dependencies from lockfile for optimal Docker layer caching in CI
COPY pyproject.toml uv.lock /tmp/devops-cli/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd /tmp/devops-cli && \
    uv export --no-dev --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --break-system-packages -r /tmp/requirements.txt pre-commit && \
    rm -rf /tmp/requirements.txt

# Copy devops-cli source files and install the package without re-downloading dependencies
COPY pyproject.toml README.md /tmp/devops-cli/
COPY src/ /tmp/devops-cli/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --no-deps /tmp/devops-cli && \
    rm -rf /tmp/devops-cli
