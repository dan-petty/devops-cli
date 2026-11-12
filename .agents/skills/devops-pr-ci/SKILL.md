---
name: devops-pr-ci
description: Run local quality gates and manage a pull request from draft to ready. Use when you verify changes or open, watch, or update a pull request.
---

# Verify Changes and Manage a Pull Request

Do not run bare `gh` commands. The `devops ci` and `devops pr` commands enforce project gates and pace GitHub requests.

## Run Local Quality Gates

1. Run `uv run devops ci test <paths>` to run tests that cover your changed files.
2. Run `uv run devops ci fail-to-pass --base origin/main` to prove that a defect test fails before your fix.
3. Run `uv run devops ci` to run the full local quality suite before you push.
4. Run `git fetch origin && git rebase origin/main` right before each push. The pre-push hook refuses a branch that does not hold `origin/main`.

## Open and Advance a Pull Request

1. Run `uv run devops pr describe <issue>` to print a valid pull request title and body.
2. Run `uv run devops pr create --title "<title>" --body "<body>"` to open the draft pull request.
3. Run `uv run devops pr monitor <number>` to wait until the remote checks settle.
4. Run `uv run devops pr threads list <number> --unresolved-only` to inspect open review threads.
5. Run `uv run devops pr threads reply <thread_id> "<body>"` to reply in a review thread.
6. Run `uv run devops pr ready <number>` to mark the pull request ready after all checks pass.
