# Design: CLI Tests for PR Edit REST Fallback and PR Update All

## Architecture and Seams

### 1. Process Edge Seam
Tests use `process_fake` to intercept CLI calls to `gh`.
- `devops pr edit`:
  - `gh pr edit` fails with exit code 1.
  - `_fallback_patch_pr` executes:
    - `gh api --method PATCH repos/owner/repo/pulls/{num} -f title=... -f body=... -f base=...`
    - `gh api --method PATCH repos/owner/repo/issues/{num} -F milestone=...`
  - Success when both succeed.
  - Failure exit when milestone PATCH returns non-zero.
- `devops pr update --all`:
  - `gh pr list --state open --author @me ...` returns JSON array of open pull requests.
  - Non-draft PRs trigger update-branch requests; draft PRs are marked `draft (skipped)`.
  - Empty PR list outputs `No open pull requests found to update.`

### 2. Request Plan Tests
- Assert the request plan of `devops pr update --all --dry-run` and `devops pr update --all --dry-run --dispatch-ci`.
- Verify no real network or mutating subprocess requests occur during dry run.
