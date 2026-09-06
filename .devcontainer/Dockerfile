FROM python:3.14-trixie

# Install standalone uv and uvx binaries into /usr/local/bin pinned to release
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /usr/local/bin/


# Copy devops-cli repository files and install system-wide into /usr/local/bin/devops
COPY pyproject.toml README.md uv.lock /tmp/devops-cli/
COPY src/ /tmp/devops-cli/src/
RUN uv pip install --system --no-cache /tmp/devops-cli && rm -rf /tmp/devops-cli
