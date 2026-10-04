# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.16@sha256:adc68cd785ca65ea25c0611043b0a00b4ea3a22e1b54102fc084406d888082ee AS uv

FROM python:3.14-slim-trixie@sha256:0741d101873c12ab927e6f8653feb8862b9bd58771177acb1b885b95141f91b4 AS builder

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --locked --no-dev --no-editable

ADD --checksum=sha256:bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386 \
    https://github.com/cli/cli/releases/download/v2.102.0/gh_2.102.0_linux_amd64.tar.gz /tmp/gh.tar.gz
RUN tar -xzf /tmp/gh.tar.gz -C /tmp && \
    install -m 755 /tmp/gh_2.102.0_linux_amd64/bin/gh /usr/local/bin/gh

FROM python:3.14-slim-trixie@sha256:0741d101873c12ab927e6f8653feb8862b9bd58771177acb1b885b95141f91b4

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

COPY --from=builder /usr/local/bin/gh /usr/local/bin/gh
COPY --from=builder /app/.venv /app/.venv

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

WORKDIR /home/devops
USER 1000:1000

EXPOSE 8000
ENTRYPOINT ["devops"]
CMD ["serve", "--host", "0.0.0.0", "--no-docs"]
