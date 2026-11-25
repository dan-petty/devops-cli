## ADDED Requirements

### Requirement: Release workflow requests owner review and Renovate avoids per-package automerge opt-outs
`.github/workflows/release.yml` SHALL include a `Request review on the release pull request` step in the `release-please` job using `steps.app.outputs.token` to request `dan-petty` on open release pull requests when the author is not `dan-petty` and `dan-petty` is not already requested. `.github/renovate.json` SHALL NOT override `automerge` to `false` on package rules, including `seaweedfs`, so approved updates merge automatically once checks pass.

#### Scenario: Release workflow and Renovate config pass validation
- **WHEN** a person or CI runs `uv run devops ci --check --only actionlint,zizmor` and `renovate-config-validator --strict --no-global .github/renovate.json`
- **THEN** both commands exit 0 and `test_release_please_makes_every_release_on_a_push_to_main` passes against `.github/workflows/release.yml`
