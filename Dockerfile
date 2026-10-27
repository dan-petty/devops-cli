# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.14-slim-trixie@sha256:0741d101873c12ab927e6f8653feb8862b9bd58771177acb1b885b95141f91b4 AS builder
ARG TARGETARCH=amd64

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken
RUN uv sync --locked --no-dev --no-editable && \
    /app/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"

ADD --checksum=sha256:77b9e297e94c50336823d0f84de7ef1be60cba704601fa0d98f129f47a94987b \
    https://github.com/cli/cli/releases/download/v2.102.1/gh_2.102.1_linux_amd64.tar.gz /tmp/gh_amd64.tar.gz
ADD --checksum=sha256:5019b3cc6e8a03bb4d88600f8dbda2add8e6407705c159b0c63151036e77a1af \
    https://github.com/cli/cli/releases/download/v2.102.1/gh_2.102.1_linux_arm64.tar.gz /tmp/gh_arm64.tar.gz
RUN tar -xzf "/tmp/gh_${TARGETARCH}.tar.gz" -C /tmp && \
    install -m 755 "/tmp/gh_2.102.1_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh && \
    rm -rf /tmp/gh*

FROM python:3.14-slim-trixie@sha256:0741d101873c12ab927e6f8653feb8862b9bd58771177acb1b885b95141f91b4 AS service

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

COPY --from=builder /usr/local/bin/gh /usr/local/bin/gh
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.cache/tiktoken /app/.cache/tiktoken

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

WORKDIR /home/devops
USER 1000:1000

EXPOSE 8000
ENTRYPOINT ["devops"]
CMD ["serve", "--host", "0.0.0.0", "--no-docs"]
