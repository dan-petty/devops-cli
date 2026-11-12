# Tasks

## 1. Behavior

- [x] 1.1 Make the pin test require `@sha256:` after the uv version of `.devcontainer/Dockerfile`, and make the limits test require `updateNotScheduled: false`. Both fail on `main`.
  - Verification: `$ uv run pytest -p no:randomly -n0 tests/core/test_renovate_config.py tests/roadmap/test_roadmap_runner_tools.py -k 'limits_keep or pins_of_the_table'`
- [x] 1.2 Pin the uv digest in `.devcontainer/Dockerfile` and set `updateNotScheduled: false` in `.github/renovate/base.json`.
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py tests/roadmap/test_roadmap_runner_tools.py`

## 2. Documents

- [x] 2.1 Say in `docs/SDLC.md` when Renovate pushes an open branch again.
  - Verification: `$ uv run devops ci docs`
