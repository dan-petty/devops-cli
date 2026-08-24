FROM python:3.14-trixie

# Install standalone uv and uvx binaries into /usr/local/bin
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install devops-cli globally
RUN pip install --no-cache-dir --break-system-packages devops-cli || true
