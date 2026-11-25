## MODIFIED Requirements

### Requirement: The smoke test of the runner image runs the tool check and bounds the size
The smoke test of the runner image in `ci.yml` and in the `Verify` job of `release-image.yml` SHALL build the stage `runner-smoke` of `smoke.Dockerfile`, which runs the tool check of the image. It SHALL then run, with the same text in both files, the tool check of a copy of the checkout and `uv run ruff --version`, `uv run pytest --version` and `uv run mypy --version` in that copy, and SHALL fail when the image is larger than 7000000000 bytes.

#### Scenario: The smoke test runs on the loaded image
- **WHEN** the Runner Image job of `ci.yml` runs its smoke test on the loaded image
- **THEN** the check module prints that every runner tool is on PATH and runs, for the image and for the checkout, the three `uv run` commands exit 0, and the step fails when `docker image inspect` reports more than 7000000000 bytes
