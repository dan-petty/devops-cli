# syntax=docker/dockerfile:1@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
# check=error=true
# The checks of the images of ./Dockerfile that a RUN step can make (#7202). Each stage starts FROM
# the image under test: by default the local tag that the example below gives it, and in a release
# the pushed digest, which a build argument gives. So both test with the same text, and a failed
# check fails the build. For example, for the Service image:
#
#   docker build --target service -t devops-cli-service:local .
#   docker build -f smoke.Dockerfile --target service-smoke .
#
# A RUN step runs as the user and with the environment of the image. It does not run the
# entrypoint, a read-only root file system or dropped capabilities, and it cannot read the size of
# the image. The `docker run` steps of ci.yml and release-image.yml make those checks. No stage of
# this file is published.
ARG SERVICE_IMAGE=devops-cli-service:local
ARG MCP_SERVER_IMAGE=devops-cli-mcp-server:local
ARG RUNNER_IMAGE=devops-cli-runner:local
ARG UV_SEED_IMAGE=devops-cli-uv-seed:local
# The image of the `devtools` stage of ./Dockerfile, whose uv and Python the runner has. The caller
# gives its reference, so this file names no version.
ARG DEVTOOLS_IMAGE=devops-cli-devtools:local

FROM ${UV_SEED_IMAGE} AS uv-seed

FROM ${DEVTOOLS_IMAGE} AS uv-seed-smoke
# hadolint ignore=DL3064
ENV UV_PYTHON=/usr/bin/python3.14 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=0 \
    UV_MALWARE_CHECK=0
# The seed is of the lock file of this checkout, and `uv sync` with no network gets the dev group
# from it.
RUN --network=none \
    --mount=type=bind,from=uv-seed,target=/seed \
    --mount=type=bind,target=/checkout <<SMOKE
set -eu
test -d /seed/cache
lock=$(sha256sum /checkout/uv.lock)
jq -e --arg lock "${lock%% *}" '.uv and .python == "3.14" and .uv_lock_sha256 == $lock' /seed/seed.json
version=$(uv --version)
version=${version#uv }
test "${version%% *}" = "$(jq -r .uv /seed/seed.json)"
cp -r /checkout /tmp/project
cp -a /seed/cache /tmp/uv-cache
export UV_CACHE_DIR=/tmp/uv-cache
timeout 60 uv --directory /tmp/project sync --locked --group dev --offline
for tool in ruff pytest mypy; do uv --directory /tmp/project run --offline "$tool" --version; done
rm -rf /tmp/project /tmp/uv-cache
SMOKE

# Every program of the image in RUNNER_TOOLS (src/devops_cli/roadmap/runner_tools.py) answers its
# version command, and the image has no compiler.
FROM ${RUNNER_IMAGE} AS runner-smoke
RUN <<SMOKE
set -eu
test "$(id -u)" = 1000
python -m devops_cli.roadmap.runner_tools
if command -v gcc; then exit 1; fi
SMOKE

FROM ${MCP_SERVER_IMAGE} AS mcp-server-smoke
RUN <<SMOKE
set -eu
test "$(id -u)" = 1000
kubectl version --client
helm version
SMOKE

# The Service image has the programs of its jobs, and no build or test tool.
FROM ${SERVICE_IMAGE} AS service-smoke
RUN <<SMOKE
set -eu
test "$(id -u)" = 1000
gh --version
git --version
openspec --version
if command -v uv; then exit 1; fi
if command -v gcc; then exit 1; fi
if python -c 'import pytest' 2>/dev/null; then exit 1; fi
SMOKE

# The checks above ran as the user of the image. This line is for the scan of this file only
# (Trivy DS-0002).
USER 1000:1000
