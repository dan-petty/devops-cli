# Proposal

## Why

Issue #2616: GitHub Actions workflow run `40812475380` on `main` failed in job `Release Please`.
The step `Merge the Release Pull Request on an Urgent Fix` evaluated `RELEASE_PR: ${{ fromJSON(steps.release.outputs.pr).number }}`.
When release-please creates a release, `steps.release.outputs.pr` is empty.
The GitHub Actions runner crashes with `Error reading JToken from JsonReader. Path '', line 0, position 0.` when it evaluates `fromJSON('')`.

## What Changes

- In `.github/workflows/release.yml`, set `RELEASE_PR: ${{ steps.release.outputs.pr }}`.
- In the step script, parse the pull request number from `$RELEASE_PR` with `jq`.
- Update `tests/test_workflow_contracts.py` to assert the updated environment variable and script behavior.
- Update `openspec/specs/release-urgent-merge/spec.md`.

## Capabilities

### Modified Capabilities

- `release-urgent-merge`: the step passes raw `steps.release.outputs.pr` as `RELEASE_PR` and parses the pull request number in the script with `jq`.

## Impact

- `.github/workflows/release.yml`
- `tests/test_workflow_contracts.py`
- `openspec/specs/release-urgent-merge/spec.md`

## Feasibility

- **Runner expression evaluation**: GitHub Actions runner evaluates template expressions in `env:` when the step is initialized.
  `fromJSON('')` throws an unhandled exception before the runner checks the step condition.
  Passing `${{ steps.release.outputs.pr }}` directly avoids `fromJSON` evaluation in the template.
- **jq parsing**: `jq -r '.number // empty'` handles empty input cleanly without failure.
  When `RELEASE_PR` contains JSON, `jq` outputs the integer pull request number.

## Existing Tool Considered

`jq` is preinstalled in the GitHub Actions runner environment and is already used in earlier lines of this step script.
Parsing with `jq` in the script body avoids template expression failure during runner initialization.
