# Tasks

## 1. Behavior

- [x] 1.1 Add `smoke.Dockerfile` with the four stages
  - Verification: `$ uv run devops ci --check --only hadolint`
- [x] 1.2 Build the stages in `ci.yml` and `release-image.yml`, and remove the `docker run` lines that they replace
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor,hadolint`

## 2. Documents

- [x] 2.1 State the stages in `CONTRIBUTING.md` and `RELEASE_CYCLE.md`
  - Verification: `$ uv run devops ci docs`
