# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: each of the four checks is a workflow of its own with the native `paths` filter, one job with its check name, no step filter and no copy in `ci.yml`; a changed file starts only the workflows whose paths it matches; the contract tests of the docs site, the image pins, the third-party scan, the Trivy pins and the rule pack read the new files; the parity allowlist of `ci.yml` drops the moved steps
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py tests/commands/test_review_rules_pack.py tests/commands/test_ci.py`
- [x] 1.2 Move the jobs to `rule-pack.yml`, `docs-site.yml`, `image-pins.yml` and `third-party-image-scan.yml`, remove the step filters, and delete the jobs from `ci.yml`
  - Verification: `$ uv run devops ci --only actionlint,zizmor`
- [x] 1.3 Name the new workflow in the `semgrep` reason of `src/devops_cli/roadmap/runner_tools.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`

## 2. Documents

- [x] 2.1 Name the new workflow files in `docs/SDLC.md`, `docs/_config.yml` and the comment of `pages.yml`
  - Verification: `$ uv run devops ci docs`
