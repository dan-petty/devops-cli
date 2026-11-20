# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM ghcr.io/astral-sh/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d AS uv

# The Node runtime that runs OpenSpec in the Service and MCP server images. Its major version is the
# one of `.node-version`. These images are on trixie, and the Node package of sid needs a newer glibc.
FROM node:24-trixie-slim@sha256:af02d57b57719b9657a45199a79264a9437940cd55b3c7b3fc99615654f124a0 AS node

# The devtools image (https://github.com/dan-petty/devtools): Debian sid with the development tools.
# Its README names the source of each tool. The runner image builds FROM it, and the Service and MCP
# server images copy single tools from it. This file names no tool version: Renovate moves the tag
# and the digest of this line, in the devtools group with the devcontainer image (#4361). The runner
# uses the OpenSpec of this image. The OpenSpec pin of the project reaches a runner Job through the
# coder bootstrap (#6517) after #6409.
FROM ghcr.io/dan-petty/devtools:20261119@sha256:a7b2f111941beaf5d36efb19f6ed2a50f8bed3062003498b97523da926143c51 AS devtools

# The runtime requirements of `uv.lock` with the `review` extra, with their hashes and without the
# project (#4550). A release changes the project version in `pyproject.toml` and `uv.lock`, but not
# this file, and BuildKit keys the cache of a `COPY --from` or a bind mount on the content of the
# files that it reads. So the dependency layers of the runner, Service and MCP server images keep
# their cache when only `src/` and the version change, and a node that holds the previous release
# pulls only the project layer.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS lock
COPY --from=uv /uv /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv export --locked --no-dev --extra review --no-emit-project --format requirements-txt \
      -o /lock/runtime.txt

# uv and the venv of the runtime requirements, for the Service and MCP server images. No file of the
# project is in this stage. Each uv install mounts the uv cache of root, so no layer holds the cache.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS deps

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken

COPY --from=lock /lock/runtime.txt /lock/runtime.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv pip sync --python /app/.venv --link-mode copy --require-hashes /lock/runtime.txt && \
    /app/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"

# The project, installed into the venv of `deps`. A change of `src/` builds this stage again. The
# Service and MCP server stages copy only the package, its dist-info and its console script from it.
FROM deps AS builder

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --extra review --link-mode copy

# OpenSpec and only the npm packages that it needs, from the Node tools of the devtools image, for
# the Service and MCP server images. The stage keeps OpenSpec alone in the package.json of the tree,
# and `npm prune` removes each package that OpenSpec does not need. The prune reads only the tree on
# disk (`--offline`) and runs no install script.
FROM devtools AS openspec
WORKDIR /usr/local/lib/openspec
RUN cp -a /usr/local/lib/devtools/npm/. . && \
    version="$(node -p 'require("./node_modules/@fission-ai/openspec/package.json").version')" && \
    npm pkg delete dependencies overrides allowScripts && \
    npm pkg set "dependencies.@fission-ai/openspec=${version}" && \
    npm prune --offline --ignore-scripts --no-audit --no-fund && \
    find node_modules -mindepth 1 -maxdepth 1 -type d -empty -delete

# The runner: the pod of a cluster Job in which `devops roadmap implement` runs its steps (#2667).
# The devtools image gives the tools that the steps, the gate and the hooks run: git, gh, uv,
# Python, Node, OpenSpec, actionlint, promtool, Trivy, OpenTofu, shellcheck, curl, jq and others.
# This stage adds the user of the Job and the venv of the runtime requirements of `uv.lock`, with
# the `review` extra. The image holds no dev dependency: the implement and fix-checks Jobs build the
# venv of their checkout with the dev group before their first agent step
# (`bootstrap_checkout` in `src/devops_cli/roadmap/runner_tools.py`, #6517). The devtools image runs
# `apt-get upgrade` of sid in its own build, and the runner takes a new devtools image each week
# through Renovate, so the runner runs no `apt-get upgrade` of its own.
# `RUNNER_TOOLS` in `src/devops_cli/roadmap/runner_tools.py` lists the programs that a Job needs,
# and the smoke test of `ci.yml` and `release.yml` checks each one of them on the image.
FROM devtools AS runner-deps

WORKDIR /app
# `uv run` in a worktree builds the venv of the worktree, from the cache on the home volume of the
# Job. The build forbids a Python download, and the `.python-version` of a checkout can name a
# patch release that the devtools image lacks, so `UV_PYTHON` names the Python of the devtools image,
# which uv uses for that minor release.
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/bin/python3.14 \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,from=lock,source=/lock/runtime.txt,target=/lock/runtime.txt \
    uv venv /app/.venv && \
    uv pip sync --python /app/.venv --link-mode copy --require-hashes /lock/runtime.txt && \
    /app/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"

# The project, installed into the venv of `runner-deps`. A change of `src/` builds this stage
# again. The runner stage copies only the package, its dist-info and its console script from it.
FROM runner-deps AS runner-builder

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --extra review --link-mode copy

# The runner stage: the dependency layers of `runner-deps` and one layer of the project. `--link`
# keeps the project layer independent of the layers under it. This stage comes before `service`,
# so that a build with no `--target` still builds the Service image. The sync of the checkout of a
# Job compiles no bytecode (`UV_COMPILE_BYTECODE=0`): Python compiles each module that a check
# imports, and the compile of all files was 71 s of the 110 s of a sync (#4814).
FROM runner-deps AS runner

COPY --link --from=runner-builder --parents /app/.venv/lib/python3.14/site-packages/devops_cli \
    /app/.venv/lib/python3.14/site-packages/devops_cli-*.dist-info /app/.venv/bin/devops /

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    UV_CACHE_DIR=/home/devops/.cache/uv \
    UV_COMPILE_BYTECODE=0 \
    PATH=/app/.venv/bin:$PATH \
    DO_NOT_TRACK=1 \
    OPENSPEC_TELEMETRY=0 \
    OPENSPEC_NO_UPDATE_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

WORKDIR /home/devops
USER 1000:1000

ENTRYPOINT ["devops"]

# The layers of the Service and MCP server images that a change of `src/` keeps: git, the Node
# runtime, gh and OpenSpec, and the venv of the runtime requirements. gh and OpenSpec come from the
# devtools image. The image holds no uv, curl or pip.
FROM python:3.14-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS service-deps

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/bin/pip*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --link --from=devtools /usr/local/bin/gh /usr/local/bin/gh
COPY --link --from=openspec /usr/local/lib/openspec /usr/local/lib/openspec
RUN ln -s ../lib/openspec/node_modules/@fission-ai/openspec/bin/openspec.js /usr/local/bin/openspec

RUN groupadd -g 1000 devops && \
    useradd -u 1000 -g 1000 -m -d /home/devops -s /bin/bash devops

RUN git config --system credential.https://github.com.helper '!gh auth git-credential' && \
    git config --system credential.https://gist.github.com.helper '!gh auth git-credential'

COPY --from=deps /app/.cache/tiktoken /app/.cache/tiktoken
COPY --from=deps /app/.venv /app/.venv

# The layers of the MCP server image that a change of `src/` keeps: those of the Service image, and
# kubectl and helm of the devtools image, which the cluster tools of the MCP server run.
FROM service-deps AS mcp-server-deps

COPY --link --from=devtools /usr/local/bin/kubectl /usr/local/bin/helm /usr/local/bin/

# The MCP server: the image of the server that serves role-scoped tool sets to cluster jobs (#3220).
# No build caches this stage (`no-cache-filters: mcp-server`), so it takes the security updates of
# the apt packages since `mcp-server-deps`, and then the project. It runs as user 1000:1000.
FROM mcp-server-deps AS mcp-server

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --link --from=builder --parents /app/.venv/lib/python3.14/site-packages/devops_cli \
    /app/.venv/lib/python3.14/site-packages/devops_cli-*.dist-info /app/.venv/bin/devops /

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken \
    PATH=/app/.venv/bin:$PATH \
    DO_NOT_TRACK=1 \
    OPENSPEC_TELEMETRY=0 \
    OPENSPEC_NO_UPDATE_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    GH_PROMPT_DISABLED=1 \
    GH_NO_UPDATE_NOTIFIER=1

WORKDIR /home/devops
USER 1000:1000

ENTRYPOINT ["devops"]

# The service stage. No build caches it (`no-cache-filters: service`), so it takes the security
# updates of the apt packages since `service-deps`, and then the project.
FROM service-deps AS service

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

COPY --link --from=builder --parents /app/.venv/lib/python3.14/site-packages/devops_cli \
    /app/.venv/lib/python3.14/site-packages/devops_cli-*.dist-info /app/.venv/bin/devops /

ENV HOME=/home/devops \
    DEVOPS_CLI_DATA_DIR=/home/devops/.data \
    TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken \
    PATH=/app/.venv/bin:$PATH \
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
