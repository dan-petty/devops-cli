# Tasks

## 1. Retry the Trivy download of the image scan steps

Reads: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/commands/test_ci.py`. Changes: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/commands/test_ci.py`.

- [x] 1.1 Update `.github/workflows/ci.yml` to set up uv toolchain, install Trivy via devops install-tools, and set skip-setup-trivy to true for image scan steps
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.2 Update `.github/workflows/release.yml` to set up uv toolchain, install Trivy via devops install-tools, and set skip-setup-trivy to true for image scan steps
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.3 Update `tests/commands/test_ci.py` allowlist to permit Install Trivy in image build jobs
  - Verification: `$ uv run pytest tests/commands/test_ci.py -k "test_ci_workflow_parity"`

## Criteria

- Group 1: Every image scan step in `.github/workflows/ci.yml` and `.github/workflows/release.yml` SHALL set `skip-setup-trivy: "true"`.
- Group 1: Every image job running Trivy scan SHALL install Trivy via `devops install-tools` before the scan step.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
