## ADDED Requirements

### Requirement: The uv-seed image pre-populates the dev dependency cache
The `Dockerfile` SHALL define a `uv-seed-build` stage `FROM devtools` before `service` that runs `uv sync --locked --group dev` with `UV_CACHE_DIR=/cache` and `UV_PYTHON=/usr/bin/python3.14` and writes `/seed.json` matching `_seed_fits`, plus a `uv-seed` stage `FROM scratch` holding `/cache` and `/seed.json`.

#### Scenario: The seed target builds and a default build still builds service
- **WHEN** `uv run devops ci --check --only hadolint` runs after adding `uv-seed-build` and `uv-seed` before `service` in `Dockerfile`
- **THEN** `hadolint` exits 0 and reports no warning or error for `Dockerfile`, and `test_service_dockerfile_base_images_pinned_by_digest` passes with `FROM scratch AS uv-seed`

### Requirement: CI validates the uv-seed target
The `mcp-server-image` job of `.github/workflows/ci.yml` SHALL bake `uv-seed` with `cache-from` pointing at `uv-seed:buildcache` and `push: false`, verify `seed.json` and an offline `--network none` sync against `devops-cli-runner:local`, and scan `devops-cli-uv-seed:local` under `trivy-image-uv-seed`.

#### Scenario: CI workflow checks accept the uv-seed bake and smoke steps
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` runs after editing `.github/workflows/ci.yml`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/ci.yml`

### Requirement: Release publishes and verifies the uv-seed image
`.github/workflows/release.yml` SHALL include `uv-seed` in its `image` matrix (`category: trivy-image-uv-seed`, `scan-exit-code: "1"`), and `.github/workflows/release-image.yml` SHALL smoke-test `seed.json` and offline `--network none` sync in `verify` when `inputs.image == 'uv-seed'`.

#### Scenario: Release workflow checks accept the uv-seed matrix entry and smoke test
- **WHEN** `uv run devops ci --check --only actionlint,zizmor` runs after editing `.github/workflows/release.yml` and `.github/workflows/release-image.yml`
- **THEN** the command exits 0 and reports no finding in `.github/workflows/release.yml` or `.github/workflows/release-image.yml`
