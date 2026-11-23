# Design

## Decisions
- Turn on auto-merge on every release pull request created or updated by release-please in `.github/workflows/release.yml`. When `steps.release.outputs.releases_created != 'true'` and `steps.release.outputs.pr != ''`, the release App token runs `gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash`.
- Retain `.github/workflows/release-merge.yml` as a scheduled background safety net to catch and merge any release pull requests that were held, retried, or missed auto-merge.

## Rejected alternatives
- Keep auto-merge restricted to urgent fixes. Rejected because non-urgent release pull requests remain open indefinitely awaiting manual intervention or the 6-hour cron, as observed on `.github/workflows/release.yml:99`: `"Pull request #$pr is not an urgent fix. A person merges the release pull request."`, leaving PR #6845 unmerged despite 10 passed checks.
- Rely only on `.github/workflows/release-merge.yml` (the 6-hour cron). Rejected because releases are delayed up to 6 hours after a passing commit on `main`, whereas arming auto-merge at release PR creation allows GitHub to merge immediately when CI completes.
