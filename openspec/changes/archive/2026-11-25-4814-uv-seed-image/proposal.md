# Proposal: #4814

## Why

The first `uv` child of an implement Job starts with an empty cache and takes 30 to 101 s (#4814). A read-only cache inside the image fails because `uv` acquires a lock on the cache directory even with `--offline`, and a wheelhouse with `UV_FIND_LINKS` or `--no-index --find-links` does not serve locked URLs or fails platform resolution. #6517 added `bootstrap_checkout` and `_seed_fits` in `src/devops_cli/roadmap/runner_tools.py` to copy `/opt/uv-seed/cache` when `/opt/uv-seed/seed.json` matches the Job's `uv`, Python minor version, and `uv.lock` hash, then run `uv sync --locked --group dev --offline` with `UV_MALWARE_CHECK=0`. No image target, CI check, or release publish exists yet for `uv-seed`.

## What Changes

- Add stages `uv-seed-build` (`FROM devtools`) and `uv-seed` (`FROM scratch`) to `Dockerfile` before `service`, running `uv sync --locked --group dev` with `UV_CACHE_DIR=/cache` and `UV_PYTHON=/usr/bin/python3.14`, writing `/seed.json` (`uv`, `python`, `uv_lock_sha256`), and copying `/cache` and `/seed.json` into `uv-seed`.
- Extend the `Runner Image` (`mcp-server-image`) job of `.github/workflows/ci.yml` to build `uv-seed` alongside `runner` and `mcp-server` in one `docker/bake-action` call without pushing, run a seed smoke test verifying `seed.json` and an offline `--network none` sync against `devops-cli-runner:local`, and scan `devops-cli-uv-seed:local` with `.github/actions/image-scan`.
- Add `uv-seed` to the `image` matrix of `.github/workflows/release.yml` and add a seed smoke step to `.github/workflows/release-image.yml` so releases push, verify, attest, and tag `ghcr.io/dan-petty/devops-cli/uv-seed`.
- Update image invariants in `tests/invariants/test_service_image.py`, `tests/invariants/test_runner_image.py`, and the run-step allowlist in `tests/commands/test_ci.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `container-image-layers`: Add the `uv-seed` OCI image build target, CI bake smoke/scan validation, and release publish/verify requirements.

## Impact

- Build & CI: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/release-image.yml`
- Tests: `tests/invariants/test_service_image.py`, `tests/invariants/test_runner_image.py`, `tests/commands/test_ci.py`
- Cluster runner mount in `k8s/devops/` remains deferred to #7072.

## Feasibility

Confirmed against `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/release-image.yml`, and `src/devops_cli/roadmap/runner_tools.py`. Both `_seed_fits` and `bootstrap_checkout` are already merged (#6517), `Dockerfile` pins `devtools` (`uv` and `/usr/bin/python3.14`), and `mcp-server-image` uses `docker/bake-action`. `tests/invariants/test_service_image.py` must allow `FROM scratch` for `uv-seed`, and `tests/invariants/test_runner_image.py` + `tests/commands/test_ci.py` must include the new `uv-seed` bake target and smoke step.

## Existing Tool Considered

Adopted `uv` cache and `--offline` mode (`https://docs.astral.sh/uv/concepts/cache/`) together with the existing `docker/bake-action` and `.github/actions/image-scan` composite action. Alternatives (`UV_FIND_LINKS` wheelhouse, `--no-index --find-links`, direct read-only cache mount, in-runner cache copy, separate Dockerfile/job) were rejected in #4814 because they either fail `uv` resolution/locking or bloat `runner` by 852 MB.
