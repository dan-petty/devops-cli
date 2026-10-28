# Proposal

## Why

Issue #2415, part 1 of #883 (owner decision 2026-10-28 on #883): a review session records no head commit and no clean-tree flag, so no code can tell a session on merged code from a session on a topic branch or a dirty tree. The hand-off of merged-code findings to roadmap intake (#2420) needs that decision.

## What Changes

- When a review starts, it reads the checkout that holds its target: the commit of `HEAD`, and whether `git status --porcelain --untracked-files=all` shows a change. `findings.json` and `candidates.json` record both as `checkout: {head, clean}`. A target outside any checkout, or in a checkout with no commit yet, records `checkout: null`.
- `devops_cli.review.checkout.is_on_merged_code(session, repository)` decides whether a session is on merged code: its subject type is `path`, its tree was clean, and `git merge-base --is-ancestor <head> origin/main` passes in `repository`. A `pr` or `branch` session, a dirty tree, a session with no checkout and a head that `origin/main` does not hold are not on merged code. A commit that the repository does not hold raises `GitOperationError`, because the repository cannot decide it.
- The recorded head is a full commit name. findings.json is a file on disk and its head goes to git as an argument, so the model refuses an option or a symbolic name.
- `devops review verify` keeps the checkout when it rewrites findings.json.
- The session's `subject` does not change, so review history keys each subject as before.
- What a review writes changes, so the change carries a spec delta: the new capability `review-merged-code`.
- This change fits one pull request. It builds no hand-off: #2419 and #2420 do.

## Capabilities

### New Capabilities

- `review-merged-code`: what a review session records about the checkout it read, and when the session is on merged code.

## Impact

- `src/devops_cli/review/checkout.py` (new), `src/devops_cli/ai/review_schema.py`, `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ai/review/runner.py`.
- `tests/review/test_review_on_merged_code.py` (new).
- `docs/SELF_IMPROVEMENT.md`, which lists what a session writes.

## Feasibility

- On origin/main d739a472, `review_subject` (`src/devops_cli/ai/review/history.py`) holds the target type, the ref and a digest of the pages. `ReviewSessionPayload` has no commit. A tool run record holds `commit` (`_tree_commit` in `src/devops_cli/security/tool_executor.py`), but only for a tool that ran and only for that tool's targets.
- git 2.55.0: `git merge-base --is-ancestor A B` exited 0 when A is an ancestor of B, 1 when it is not, and 128 with "fatal: Not a valid commit name" for a commit the repository does not hold. `git rev-parse --verify --quiet HEAD` exits 1 in a checkout with no commit. `--no-optional-locks` keeps `git status` from writing the index of the reviewed checkout.
- `devops review path <dir> --reporting-only` ran in a test with no model call and wrote findings.json and candidates.json, so the acceptance test runs the real command against a real temporary repository.

## Existing Tool Considered

git gives every fact: `rev-parse`, `status --porcelain` and `merge-base --is-ancestor`. The change builds no tool of its own: one model with two fields, one reader and one predicate. It deletes no code.
