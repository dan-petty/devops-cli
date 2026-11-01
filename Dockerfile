# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

# The Node runtime of the pinned OpenSpec. Its major version is the one of `.node-version`.
FROM node:24-trixie-slim@sha256:54f84b4cf8432b21aaffd5d3ce8d41e12cea0d10d33c09d2f3c9879d49d6b446 AS node

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

# OpenSpec, as `devops install-tools` installs it: `npm ci` from the lockfile of
# `src/devops_cli/tools_lock/openspec`, which checks the sha512 of every package. The tool goes to
# /opt/devops-tools, and the service stage copies that directory to the same path. The installer
# makes the version directory private to its user, so the chmod lets the Service user read it.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --tool openspec --target-dir /opt/devops-tools/bin && \
    chmod -R a+rX /opt/devops-tools

# The runner: the pod of a cluster Job in which `devops roadmap implement` runs its steps (#2667).
# It adds to the builder's venv the dev dependencies that the steps' tests and checks run (pytest,
# ruff, mypy, pre-commit and the rest of the dev group), and git, which a step and the job need. The
# builder holds uv, gh, the Node runtime and the pinned OpenSpec already. The stage adds the tools
# that the gate and the hooks need (#3072): curl and jq from apt, and promtool at its pin in
# `tools.lock`. actionlint, shellcheck and Trivy are not here: the image scan fails on the newest
# release of each (see `NOT_IN_RUNNER`). The list of the tools is `RUNNER_TOOLS` in
# `src/devops_cli/roadmap/runner_tools.py`, and the last step of the stage checks every one of them. This stage comes before `service`, so that a build with no
# `--target` still builds the Service image.
FROM builder AS runner

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# The pinned binary goes where OpenSpec went, from the same lock and with the same checksum check.
# It is not in the builder stage, so the Service image does not hold it.
RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --tool promtool --target-dir /opt/devops-tools/bin && \
    chmod -R a+rX /opt/devops-tools

# A Job installs no tool, so npm goes (it bundles `undici` and `brace-expansion`) and so does pip
# (it vendors `certifi`, `urllib3` and `msgpack`), as in the service stage. The scan of the image
# reports all of them. The uv cache of root, which holds the wheels of the build, goes too.
RUN uv sync --locked --no-editable && \
    rm -rf /root/.cache/uv /usr/local/lib/node_modules/npm /usr/local/bin/npm \
      /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

# `uv run` in a worktree builds the worktree's own venv, from the cache below, which the Job's
# home volume holds: the root filesystem of the Job is read-only. The builder forbids a Python
# download, and the `.python-version` of a checkout can name a patch release that this base image
# lacks, so `UV_PYTHON` names the image's own interpreter, which uv uses for that minor release.
ENV HOME=/home/devops \
    UV_PYTHON=/usr/local/bin/python3 \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    UV_CACHE_DIR=/home/devops/.cache/uv \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken \
    PATH=/app/.venv/bin:/opt/devops-tools/bin:$PATH \
    DO_NOT_TRACK=1 \
    OPENSPEC_TELEMETRY=0 \
    OPENSPEC_NO_UPDATE_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

WORKDIR /home/devops
USER 1000:1000

# The smoke test of the stage: every tool of `RUNNER_TOOLS` runs, and every tool of the lock links at
# its locked version. A tool that is missing, or at another version than its pin, fails the build.
RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools python -m devops_cli.roadmap.runner_tools

ENTRYPOINT ["devops"]

FROM python:3.14-slim-trixie@sha256:0741d101873c12ab927e6f8653feb8862b9bd58771177acb1b885b95141f91b4 AS service

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=builder /usr/local/bin/gh /usr/local/bin/gh
COPY --from=builder /opt/devops-tools /opt/devops-tools
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/.cache/tiktoken /app/.cache/tiktoken

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken \
    PATH=/app/.venv/bin:/opt/devops-tools/bin:$PATH \
    DO_NOT_TRACK=1 \
    OPENSPEC_TELEMETRY=0 \
    OPENSPEC_NO_UPDATE_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

WORKDIR /home/devops
USER 1000:1000

EXPOSE 8000
ENTRYPOINT ["devops"]
CMD ["serve", "--host", "0.0.0.0", "--no-docs"]
