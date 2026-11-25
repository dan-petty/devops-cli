## MODIFIED Requirements

### Requirement: The uv-seed image pre-populates the dev dependency cache
The `Dockerfile` SHALL define, before `service`, a `uv-seed-build` stage `FROM devtools` that fills `/cache` from the dev requirements and the stub project that the `lock` stage gives, and a `uv-seed` stage `FROM scratch` that holds `/cache` and a `/seed.json` matching `_seed_fits`. A change of the project version MUST NOT change the cache layer.

#### Scenario: The seed target builds and a default build still builds service
- **WHEN** `uv run devops ci --check --only hadolint` runs after adding `uv-seed-build` and `uv-seed` before `service` in `Dockerfile`
- **THEN** `hadolint` exits 0 and reports no warning or error for `Dockerfile`, and `test_service_dockerfile_base_images_pinned_by_digest` passes with `FROM scratch AS uv-seed`

#### Scenario: A checkout syncs from the seed with no network
- **WHEN** the stage `uv-seed-smoke` of `smoke.Dockerfile` runs on the seed
- **THEN** `uv sync --locked --group dev --offline` exits 0, and `ruff`, `pytest` and `mypy` run

#### Scenario: A release keeps the cache layer
- **WHEN** a person builds `--target uv-seed`, changes only the project version in `pyproject.toml` and `uv.lock`, and builds it again
- **THEN** the build takes the cache layer from cache, and the digest of that layer is the same
