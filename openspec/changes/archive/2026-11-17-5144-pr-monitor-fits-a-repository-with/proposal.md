# Proposal: #5144

## Why

`devops pr monitor` and `devops pr check-readiness` take the head commit of a pull request with no
check as a running check. In a repository with no GitHub Actions workflow no check will start, so
`check-readiness` exits 1 with a pending-check blocker and `pr monitor` waits until its timeout and
exits 3. Pull request #5142 (#3767) excused that case for `devops pr ready` only. Closes #5144.

## What Changes

- The merge-readiness verdict reads the workflows at the head commit and their triggers. A
  repository with no workflow, or none that lists `pull_request` or `pull_request_target`, has no
  CI for the pull request.
- The verdict adds an INFO advisory and no pending-check blocker when no workflow can start a
  check on the pull request, so `devops pr check-readiness` exits 0 and `devops pr monitor`
  settles on its first poll.
- `devops pr ready` uses the same verdict instead of `GitHubClient.count_workflows`.
- A workflow read that fails keeps the pending check, so all three commands fail closed.

## Capabilities

### Modified

- `pr-merge-readiness`: the verdict, `devops pr check-readiness`, `devops pr ready` and
  `devops pr monitor` share one no-CI decision.

## Impact

`devops pr check-readiness`, `devops pr ready` and `devops pr monitor` no longer wait for a check
that a repository without a pull-request workflow cannot start. `GitHubClient.count_workflows` is
removed, since its branch-wide count ignores the triggers and the head commit.

## Feasibility

Confirmed against the issue and the code at `origin/main`: `_judge_checks` in
`src/devops_cli/github/merge_readiness.py` holds the pending stand-in, `_no_ci` in
`src/devops_cli/commands/pr.py` used `GitHubClient.count_workflows`, and
`CheckVerdictSummary.reports_nothing` detects the stand-in. `GitHubClient.get_file_at` already
reads a file at a ref, and PyYAML is a project dependency.

## Existing Tool Considered

No open tool or library covers this need. The change uses the existing GitHub contents endpoint
and PyYAML, adds no dependency, and costs about 8,000 tokens and one engineer-day to build and
test.
