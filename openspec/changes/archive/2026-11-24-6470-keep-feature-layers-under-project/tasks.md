# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests for Dockerfile stages and action build configuration
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py -k test_the_release_attests_and_tags_only_the_devcontainer_digest_its_smoke_test_started`
- [x] 1.2 Implement `base`, `builder`, and `project` stages with `ARG BASE_IMAGE=base` in `.devcontainer/Dockerfile`
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py -k test_the_release_attests_and_tags_only_the_devcontainer_digest_its_smoke_test_started`
- [x] 1.3 Update `.github/actions/devcontainer-image/action.yml` to build Feature image first and project stage second
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py -k test_the_release_attests_and_tags_only_the_devcontainer_digest_its_smoke_test_started`

## 2. Documents

- [x] 2.1 Update `docs/SDLC.md` and `docs/DEVCONTAINER_USAGE.md`
  - Verification: `$ uv run devops ci docs`
