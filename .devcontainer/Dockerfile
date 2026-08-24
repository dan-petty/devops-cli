FROM python:3.14-trixie

# Install standalone uv and uvx binaries into /usr/local/bin
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install devops-cli system-wide using uv
RUN uv pip install --system --no-cache devops-cli || true
