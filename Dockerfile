# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 AS uv

# The Node runtime of the pinned OpenSpec. Its major version is the one of `.node-version`.
FROM node:24-trixie-slim@sha256:af02d57b57719b9657a45199a79264a9437940cd55b3c7b3fc99615654f124a0 AS node

# The requirements of `uv.lock`, with their hashes and without the project (#4550). A release
# changes the project version in `pyproject.toml` and `uv.lock`, but not these two files, and BuildKit
# keys the cache of a `COPY --from` on the content of the files that it copies. So the dependency
# layers under the `runner` and `service` stages keep their cache when only `src/` and the version
# change, and a node that holds the previous release pulls only the new project layer.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS lock
COPY --from=uv /uv /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --locked --no-dev --extra review --no-emit-project --format requirements-txt \
      -o /lock/runtime.txt && \
    uv export --locked --only-dev --no-emit-project --format requirements-txt -o /lock/dev.txt

# uv, gh and the venv of the runtime requirements. No file of the project is in this stage. Each uv
# install mounts the uv cache of root, so no layer holds the cache.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS deps
ARG TARGETARCH=amd64

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken

# gh, from its pinned release. BuildKit `ADD` of a URL has no retry option, so a 504 answer of GitHub
# failed the build (#4223). The step fetches the tarball with `curl --retry` instead, and it checks
# the pinned SHA-256 with `sha256sum`. The Service image copies gh from this stage, but not curl.
RUN apt-get update && apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
      ca-certificates curl && \
    rm -rf /var/lib/apt/lists/* && \
    case "${TARGETARCH}" in \
      amd64) \
        url="https://github.com/cli/cli/releases/download/v2.103.3/gh_2.103.3_linux_amd64.tar.gz"; \
        sha=4c806978ffce1cec70853302a56d70ac6da4f19bae7adca4e1a8ab00633dd91d ;; \
      arm64) \
        url="https://github.com/cli/cli/releases/download/v2.103.3/gh_2.103.3_linux_arm64.tar.gz"; \
        sha=ee32df2323c8847f5fac6cb6b4b69ca75828e9329a8f22f677021f7b3306ce63 ;; \
      *) echo "no gh build for ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL --retry 8 --retry-all-errors --retry-delay 2 -o /tmp/gh.tar.gz "$url" && \
    echo "$sha  /tmp/gh.tar.gz" | sha256sum -c - && \
    tar -xzf /tmp/gh.tar.gz -C /tmp && \
    install -m 755 "/tmp/gh_2.103.3_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh && \
    rm -rf /tmp/gh*

COPY --from=lock /lock/runtime.txt /lock/runtime.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv pip sync --python /app/.venv --link-mode copy --require-hashes /lock/runtime.txt && \
    /app/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"

# The project, installed into the venv of `deps`, and the tools that `devops install-tools` installs
# from `tools.lock`. A change of `src/` builds this stage again. The final stages copy only the
# package, its dist-info and its console script from it, and the stages under them copy the tool
# directory, which is the same after such a change.
FROM deps AS builder

# OpenSpec, as `devops install-tools` installs it: `npm ci` from the lockfile of
# `src/devops_cli/tools_lock/openspec`, which checks the sha512 of every package. The tool goes to
# /opt/devops-tools, and `service-deps` copies that directory to the same path. The installer
# makes the version directory private to its user, so the chmod lets the Service user read it.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --extra review --link-mode copy

RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --tool openspec --target-dir /opt/devops-tools/bin && \
    chmod -R a+rX /opt/devops-tools

# The pinned promtool goes where OpenSpec went, from the same lock and with the same checksum check.
# The Service image does not hold it, so it has its own stage, which `runner-deps` copies.
FROM builder AS runner-tools
RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --tool promtool --target-dir /opt/devops-tools/bin && \
    chmod -R a+rX /opt/devops-tools

# The runner: the pod of a cluster Job in which `devops roadmap implement` runs its steps (#2667).
# `runner-deps` adds to the venv of `deps` the dev requirements that the steps' tests and checks
# run (pytest, ruff, mypy, pre-commit and the rest of the dev group), and git, which a step and
# the job need. `deps` holds uv and gh. The stage adds the tools that the gate and the hooks need
# (#3072): curl and jq from apt, the Node runtime, and OpenSpec and promtool at their pins in
# `tools.lock`. actionlint, shellcheck and Trivy are not here: the image scan fails on the newest
# release of each (see `NOT_IN_RUNNER`). The list of the tools is `RUNNER_TOOLS` in
# `src/devops_cli/roadmap/runner_tools.py`, and the last step of the `runner` stage checks every
# one of them. A Job installs no tool, so the image holds no npm, and pip goes (it vendors
# `certifi`, `urllib3` and `msgpack`), as in the service stage: the scan of the image reports them.
FROM deps AS runner-deps

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

COPY --from=runner-tools /opt/devops-tools /opt/devops-tools

COPY --from=lock /lock/dev.txt /lock/dev.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/.venv --link-mode copy --require-hashes --no-deps -r /lock/dev.txt

# The runner stage. No build caches it (`no-cache-filters: runner`), so it takes the security
# updates of the apt packages since `runner-deps`, and then the project. This stage comes before
# `service`, so that a build with no `--target` still builds the Service image.
FROM runner-deps AS runner

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --from=builder --parents /app/.venv/lib/python3.14/site-packages/devops_cli \
    /app/.venv/lib/python3.14/site-packages/devops_cli-*.dist-info /app/.venv/bin/devops /

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

# The MCP server: image for the MCP server that serves role-scoped tool sets to cluster jobs (#3220).
# Inherits runner, installs kubectl and helm at their pinned versions, and runs as user 1000:1000.
FROM runner AS mcp-server

USER root

RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --tool kubectl --target-dir /opt/devops-tools/bin && \
    DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --tool helm --target-dir /opt/devops-tools/bin && \
    chmod -R a+rX /opt/devops-tools

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    UV_CACHE_DIR=/home/devops/.cache/uv

USER 1000:1000

# The tool version check of the stage: kubectl and helm run at their locked versions.
RUN DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --check --tool kubectl --target-dir /opt/devops-tools/bin && \
    DEVOPS_CLI_USER_DATA_ROOT=/opt/devops-tools /app/.venv/bin/devops install-tools \
      --check --tool helm --target-dir /opt/devops-tools/bin

# The layers of the Service image that a change of `src/` keeps: git, the Node runtime, gh, OpenSpec
# and the venv of the runtime requirements. The image holds no uv, curl or pip.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS service-deps

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=deps /usr/local/bin/gh /usr/local/bin/gh

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

COPY --from=deps /app/.cache/tiktoken /app/.cache/tiktoken
COPY --from=builder /opt/devops-tools /opt/devops-tools
COPY --from=deps /app/.venv /app/.venv

# The service stage. No build caches it (`no-cache-filters: service`), so it takes the security
# updates of the apt packages since `service-deps`, and then the project.
FROM service-deps AS service

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --from=builder --parents /app/.venv/lib/python3.14/site-packages/devops_cli \
    /app/.venv/lib/python3.14/site-packages/devops_cli-*.dist-info /app/.venv/bin/devops /

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
