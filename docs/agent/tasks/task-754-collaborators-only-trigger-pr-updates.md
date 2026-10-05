# Task: Only Collaborators Can Trigger PR Updates with /update or /sync Comments (#754)

**Issue**: [#754](https://github.com/dan-petty/devops-cli/issues/754)
**Status**: Done
**Milestone**: v0.2.27
**Priority**: priority/p1-high
**Scope**: scope/ci

## Description
`.github/workflows/update-prs.yml` previously ran `devops pr update <PR>` for any pull request comment whose body started with `/update` or `/sync` without checking commenter authorization. Because the repository is public, any account could trigger branch updates and consume Actions runner time. Furthermore, values in `run:` blocks were directly interpolated using `${{ ... }}` expressions rather than being passed securely through step `env:` variables.

This change delivers:
1. **Collaborator Authorization Guard**: Extended the job-level `if:` in `.github/workflows/update-prs.yml` so that `issue_comment` triggers require `contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)`. Unauthorized comments produce skipped jobs without runner consumption.
2. **Expression Isolation in `run:`**: Moved all nine `${{ ... }}` expressions out of `run:` script blocks into step `env:` variables, completely eliminating shell injection vectors.
3. **Workflow Contract Tests**: Added `tests/test_workflow_contracts.py` verifying the collaborator guard, expression isolation, permission boundaries (`contents: write`, `pull-requests: write`, `issues: write`; no `actions: write`), and mutation cases.

## Acceptance Criteria
- [x] `uv run pytest tests/test_workflow_contracts.py -q` passes, verifying that the `update-pull-requests` job condition requires `github.event.comment.author_association` matching `OWNER`, `MEMBER`, or `COLLABORATOR`, while preserving `push` and `workflow_dispatch` events.
- [x] Contract tests verify that no step in `update-prs.yml` interpolates expressions inside `run:` blocks, with occurrences restricted to `concurrency.group` and step `env:` variables.
- [x] Mutation tests verify that removing the author association check or re-introducing inline expressions into `run:` blocks causes immediate test failure.
- [x] `uv run actionlint` exits 0 on `.github/workflows/update-prs.yml`.
- [x] `uv run devops ci` passes offline with 100% green status across all quality gates.
- [x] `git diff` against base branch lists only `.github/workflows/update-prs.yml`, `tests/test_workflow_contracts.py`, `docs/agent/tasks/task-754-collaborators-only-trigger-pr-updates.md`, and `changelog.d/754.md`.
- [x] `update-prs.yml` preserves the 4 `uv run devops pr update` invocations, step order, and minimal permissions.
- Pending a person: after merge, comment `/update` on an open PR from the owner account, then run `gh run list --workflow update-prs.yml --limit 3` and see a completed run and the rocket reaction on the comment. When an account without write access next comments `/update` or `/sync` on a PR, the Actions tab lists that run as skipped.

## Deliverables
- [x] Collaborator guard in `.github/workflows/update-prs.yml`
- [x] Secure `env:` variable mapping for all `${{ ... }}` expressions in `update-prs.yml`
- [x] Contract test suite `tests/test_workflow_contracts.py`
- [x] Changelog fragment `changelog.d/754.md`
- [x] Task file `docs/agent/tasks/task-754-collaborators-only-trigger-pr-updates.md`
