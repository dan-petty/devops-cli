# syntax=docker/dockerfile:1@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
# check=error=true

ARG BASE_IMAGE=base

# The devcontainer image: the devtools image, the venv of devops-cli and the project. Each tool
# comes from the devtools image (https://github.com/dan-petty/devtools), which names the source
# of each tool. This file pins the image by digest, and Renovate moves the digest. The two Dev
# Container Features of .devcontainer/image/devcontainer.json add the user vscode and Podman.
FROM ghcr.io/dan-petty/devtools:1.2.4@sha256:f186a476cc8ce6c18a5855db4a7841825510fcb4f49bf03bc7b7ef81538371c3 AS devtools

# The requirements of `uv.lock`, with their hashes and without the project (#4550). A release
# changes the project version in `pyproject.toml` and `uv.lock`, but not this file, and BuildKit
# keys the cache of a mount from this stage on the content of the file. So the venv layer keeps its
# cache when only `src/` and the version change.
FROM devtools AS lock
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN UV_PYTHON_DOWNLOADS=never uv export --locked --no-dev --extra review --no-emit-project \
      --format requirements-txt -o /lock/requirements.txt

# The venv of the runtime requirements in /opt/devops-cli/.venv, which is outside the home volume.
# `--require-hashes` refuses a distribution that the lock does not name with its hash. This stage
# writes the tiktoken encodings to /usr/local/share/tiktoken (TIKTOKEN_CACHE_DIR), so `devops`
# counts tokens with no download. /run/user/1000 holds the container-local session bus of
# gnome-keyring; /tmp is shared.
FROM devtools AS venv
# hadolint ignore=DL3064
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/usr/local/share/tiktoken
RUN install -d -m 0700 -o 1000 -g 1000 /run/user/1000
RUN --mount=type=bind,from=lock,source=/lock/requirements.txt,target=/tmp/requirements.txt \
    --mount=type=cache,target=/root/.cache/uv \
    UV_PYTHON_DOWNLOADS=never uv venv --python /usr/bin/python3 /opt/devops-cli/.venv \
    && uv pip sync --python /opt/devops-cli/.venv/bin/python --require-hashes /tmp/requirements.txt \
    && /opt/devops-cli/.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')"

# The base stage: base tools and venv without the project package. The Dev Containers CLI builds
# this stage with its Features (.devcontainer/image/devcontainer.json) so the Feature layers land
# on this stage, before the project layer (#6470).
FROM venv AS base
ENV PATH="${PATH}:/opt/devops-cli/.venv/bin"
# hadolint ignore=DL3066
USER vscode

# The project, built and installed into the venv. A change of `src/` builds this stage again; the
# project stage copies from it only the package, its dist-info and its console script.
FROM venv AS builder
COPY pyproject.toml README.md /tmp/devops-cli/
COPY src/ /tmp/devops-cli/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/devops-cli/.venv/bin/python --no-deps /tmp/devops-cli

# Only the Dev Containers CLI of the devtools image. The build action
# (.github/actions/devcontainer-image) exports this stage to the runner and builds the image with
# it, so the digest above also pins the CLI. No other stage uses it.
FROM scratch AS devcontainers-cli
COPY --from=devtools /usr/local/lib/devtools/npm/node_modules/@devcontainers/cli /

# Only the commands of the devtools image that the CI jobs on the runner host run (#6416). The
# action .github/actions/devtools-commands exports this stage on a miss of its cache and copies the
# commands that a job names to a directory, which the job puts on PATH, so the digest above also
# pins each command. No other stage uses it.
FROM scratch AS devtools-bin
COPY --from=devtools /usr/local/bin/gitleaks /usr/local/bin/helm /usr/local/bin/kube-linter \
    /usr/local/bin/kubectl /usr/local/bin/osv-scanner /usr/local/bin/promtool /usr/local/bin/tofu \
    /usr/local/bin/trivy /usr/local/bin/tuicr /

# This copy is the devops of the published image: a child repository's post-create and post-start
# run it, and so does this repository's first post-create, before `uv sync` fills .venv. The venv
# is the last directory of PATH, so its python does not hide the python of the system. The
# remoteEnv PATH of .devcontainer/devcontainer.json puts .venv/bin first, so in this repository
# `devops` is the editable install of the checkout (#2449). The project layer is the last layer of
# this file, and `--link` makes it independent of the layers under it. In CI, BASE_IMAGE points to
# the Feature image built from `base`, so the Feature layers stay under the project layer (#6470).
FROM ${BASE_IMAGE} AS project
COPY --link --from=builder --parents /opt/devops-cli/.venv/lib/python3.*/site-packages/devops_cli \
    /opt/devops-cli/.venv/lib/python3.*/site-packages/devops_cli-*.dist-info \
    /opt/devops-cli/.venv/bin/devops /
# hadolint ignore=DL3066
USER vscode
