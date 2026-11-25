# Design

## Decisions

- **Build `uv-seed-build` from `devtools` and copy into `FROM scratch AS uv-seed` before `service`.**
  - `_seed_fits` in `src/devops_cli/roadmap/runner_tools.py` compares `uv --version`, `<major>.<minor>` of Python, and the sha256 of `uv.lock`. Building `uv-seed-build` from `devtools` with `UV_PYTHON=/usr/bin/python3.14`, `UV_PYTHON_DOWNLOADS=never`, `UV_CACHE_DIR=/cache`, and `UV_COMPILE_BYTECODE=0` guarantees the cached wheels and `uv` layout match the `runner` stage. Placing both stages before `service` ensures a default `docker build .` still builds `service`. Making `/cache` and `/seed.json` world-readable (`chmod -R a+rX`) lets non-root uid `1000` copy them in smoke tests and runner pods.
- **Write `/seed.json` inline with `/usr/bin/python3.14` in the `uv-seed-build` `RUN` step.**
  - Computing the `uv` version token, Python `<major>.<minor>`, and `uv.lock` sha256 with `/usr/bin/python3.14` uses the exact field names and derivation logic of `_seed_fits` with no extra helper script.
- **Extract and verify the `uv-seed` image with `docker create <image> true` and `docker cp`.**
  - A `FROM scratch` image holds no shell binary, so `docker create ... true` + `docker cp` extracts `/seed.json` and `/cache` reliably across Docker and Podman. In `ci.yml`, `Run UV Seed Image Smoke Test` mounts the extracted seed at `/opt/uv-seed:ro` in `devops-cli-runner:local` with `--network none` and runs `_seed_fits`, `python -m devops_cli.roadmap.runner_tools`, and `uv run --offline` within 60 s. In `release-image.yml`, `Verify` pulls the `devtools` image pinned in `Dockerfile` first, then verifies `/seed.json` and runs offline `uv sync --locked --group dev --offline` with `--network none` within 60 s.
- **Keep registry cache and Trivy scan parity.**
  - `ci.yml` reads `ghcr.io/${REPOSITORY}/uv-seed:buildcache` and writes none; `release-image.yml` reads and writes `uv-seed:buildcache`. Both scan `uv-seed` under category `trivy-image-uv-seed` with exit code `1` because `uv-seed` holds no `devtools` Go binaries.
- **Exempt Docker's reserved `scratch` base in `_unpinned_dockerfile_images`.**
  - `scratch` has no registry manifest or `@sha256:` digest, so `tests/invariants/test_service_image.py` skips `scratch` while continuing to require `@sha256:` or an earlier stage name on every other `FROM`.

## Rejected alternatives

- **Embedding `/opt/uv-cache` in `runner`**: Adds ~852 MB to the runner image and couples runner image updates to lockfile wheel cache bloat.
- **Using `FROM ghcr.io/astral-sh/uv` in `uv-seed-build`**: Can diverge from the `uv` version installed in `devtools`, causing `_seed_fits` to fall back online.
- **Running `docker run` directly on `uv-seed`**: Impossible on `FROM scratch` without bundled binaries; extraction via `docker create` and `docker cp` tests the exact OCI payload.
