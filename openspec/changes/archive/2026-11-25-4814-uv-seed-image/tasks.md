# Tasks

## 1. Update image and CI invariants first

Kind: other. Reads: `tests/invariants/test_runner_image.py`, `tests/invariants/test_service_image.py`, `tests/commands/test_ci.py`, `Dockerfile`, `.github/workflows/ci.yml`. Changes: `tests/invariants/test_runner_image.py`, `tests/invariants/test_service_image.py`, `tests/commands/test_ci.py`.

- [x] 1.1 Update `tests/invariants/test_runner_image.py` so `test_the_pull_request_check_builds_the_runner_image_and_pushes_nothing` requires `uv-seed` in `docker/bake-action` targets, `target "uv-seed"` and its `cache-from` ref in `Write Docker Bake Definition`, and `Run UV Seed Image Smoke Test` plus `Scan UV Seed Image for Vulnerabilities` in `mcp-server-image`; verify it fails against `origin/main` before workflow edits
  - Verification: `$ uv run pytest tests/invariants/test_runner_image.py`
- [x] 1.2 Update `_unpinned_dockerfile_images` in `tests/invariants/test_service_image.py` to permit Docker's reserved `scratch` base while keeping digest pinning enforced for all other images, and add `("mcp-server-image", "Run UV Seed Image Smoke Test")` to the run-step allowlist in `tests/commands/test_ci.py`
  - Verification: `$ uv run pytest tests/invariants/test_service_image.py tests/commands/test_ci.py`

## 2. Add uv-seed target and CI/release wiring

Kind: other. Reads: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/release-image.yml`. Changes: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/release-image.yml`.

- [x] 2.1 Add `uv-seed-build` (`FROM devtools`) and `uv-seed` (`FROM scratch`) stages before `service` in `Dockerfile` running `uv sync --locked --group dev` into `/cache` and writing `/seed.json` matching `_seed_fits`
  - Verification: `$ uv run devops ci --check --only hadolint`
- [x] 2.2 Update `.github/workflows/ci.yml`, `.github/workflows/release.yml`, and `.github/workflows/release-image.yml` to bake, smoke-test offline (`--network none`), scan (`trivy-image-uv-seed`), attest, and tag `uv-seed`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`

## 3. Full local validation

Kind: other. Reads: `Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/release-image.yml`, `tests/invariants/test_runner_image.py`, `tests/invariants/test_service_image.py`, `tests/commands/test_ci.py`. Changes: none.

- [x] 3.1 Run the affected pytest suites and non-test CI gates (`hadolint`, `actionlint`, `zizmor`, `test-tree`, `openspec`, etc.) after archiving the change
  - Verification: `$ uv run devops ci --check --skip test --force`
