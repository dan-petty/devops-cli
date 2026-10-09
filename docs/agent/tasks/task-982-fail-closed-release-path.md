# Task: One fail-closed release path: cut branch from remote release tip, uv.lock bump, draft flag, required label and milestone (#982)

**Issue**: [#982](https://github.com/dan-petty/devops-cli/issues/982)
**Status**: Done
**Milestone**: v0.2.26
**Priority**: priority/p1-high
**Scope**: type/fix, scope/release, priority/p1-high

## Description
Delivers one shared, fail-closed release cut function in `src/devops_cli/commands/release.py` (`cut_release`), called by `devops release prepare <version> --create-pr`, `devops release pr`, and #743's `devops roadmap close`.
It validates git cleanliness before any branch or file is touched, fetches `origin`, builds `chore/cut-v<version>` from `origin/release/v<version>`, performs edits on the cut branch (`pyproject.toml`, `src/devops_cli/__init__.py`, `uv.lock`, the in-cluster service image tag, and doc sync), commits and pushes to `origin chore/cut-v<version>` with `--force-with-lease`, and opens the release pull request into `main` with required label `release` and milestone `v<version>`. If any step fails (e.g. dirty working tree, missing remote release branch, push rejected by git remote hook, or `gh pr create` rejecting label/milestone), the process exits non-zero and fails closed immediately without fallback retries or opening a PR.

## Acceptance Criteria
- [x] `devops release prepare 0.2.26 --create-pr` on a dirty tree exits non-zero naming the dirty state; no branch is created and no file changes (`git status --porcelain` is unchanged).
- [x] On a clean clone checked out on another branch, the run pushes `chore/cut-v0.2.26` to the bare remote; its parent commit is the remote `release/v0.2.26` tip, and the remote `release/v0.2.26` and `main` do not move.
- [x] With `origin/release/v0.2.26` absent, the run exits non-zero naming the branch; the tree stays clean and no branch is created.
- [x] After one more commit is pushed to the remote `release/v0.2.26` and the remote `chore/cut-v0.2.26` already exists, a second run rebuilds the cut branch on the new tip and the push replaces the old branch.
- [x] With `--no-sync-docs`, the cut commit changes exactly `pyproject.toml`, `src/devops_cli/__init__.py` (where it holds the version) and `uv.lock`. `CHANGELOG.md` and `changelog.d/` are byte-identical to the release tip (`git show --stat`).
- [x] After the bump, `uv lock --check --offline` passes on a temporary copy of `pyproject.toml` and `uv.lock` with an empty `UV_CACHE_DIR` (skipped when `uv` is not on `PATH`).
- [x] In a root without `uv.lock`, the run neither creates one nor stages it.
- [x] The `gh pr create` invocation receives base `main`, head `chore/cut-v0.2.26`, title `feat(release): v0.2.26`, `--label release`, `--milestone v0.2.26`, and `--draft` by default; with `--no-draft`, and when the shared function is called with `draft=False`, no `--draft`.
- [x] When the bare remote's `pre-receive` hook rejects the push, the run exits non-zero and `gh pr create` is never called.
- [x] When `gh pr create` fails naming the label, or naming the milestone, the run exits non-zero and `gh pr create` is called once (replacing `test_release_pr_labels_and_draft` and the gh-failure branch of `test_release_pr_error_branches_and_breaking`).
- [x] `devops release pr` alone on a clean tree pushes a cut branch equal to the remote release tip and opens the PR whose title names the version in the tip's `pyproject.toml`, not the caller's checkout; on a dirty tree it exits non-zero before any git write.
- [x] `devops release pr --help` lists no `--push`; `rg -n "no-push"` finds nothing in `src`, `docs/commands/release.md`, or `docs/CLI_REFERENCE.md`.
- [x] `release prepare 0.2.26 --create-pr --dry-run` and `release pr --dry-run` print the cut branch `chore/cut-v0.2.26`, base `main`, the title and the fragments; no git ref changes and `gh` is not called.
- [x] Across these tests the fake `gh` never receives `pr merge` or `pr review`; the bare remote's `release/**` and `main` refs are unchanged after every test.
- [x] `chore/cut-v0.2.25` from this repository into `main` is exempt from grounding before any lookup; `release/v0.2.25` into `main`, a fork's `chore/cut-v0.2.25` into `main`, and `chore/cut-v0.2.25` into `release/v0.2.25` are held to grounding.
- [x] `chore/open-v0.2.25` and `chore/open-v0.2.25-cycle` into `release/v0.2.25` stay exempt.
- [x] `.github/labels.yml` declares `release`; `test_repository_labels_declare_the_release_label` in `tests/test_github_labels.py` loads the repository's file with `load_label_specs` and asserts `DEFAULT_RELEASE_LABEL` is among the names.
- [x] `_build_pr_fallback_cmd`, `_strip_pr_cmd_flag`, and `_checkout_release_branch` are removed from `src`, `tests`, and `docs`.
- [x] Updated convention sentences in `AGENTS.md`, `RELEASE_CYCLE.md`, `docs/agent/tasks/README.md`, and `src/devops_cli/config/constants.py` to specify `chore/cut-vX.Y.Z` into `main`.
- [x] `docs/ROUTINE_TASKS.md` has no "Creates topic branch `release/v<version>`" sentence and no "Initialize `## [Unreleased]`" step.
- [x] `uv run devops docs check` passes; `uv run devops ci` passes.
- Pending a person: `uv run devops release prepare 0.2.26 --create-pr --dry-run` from a clean clone of `release/v0.2.26` prints the cut branch and base; the first real v0.2.26 cut (through #743 or by hand) gives `gh pr view <n> --json headRefName,baseRefName,labels,milestone` with head `chore/cut-v0.2.26`, base `main`, label `release`, milestone `v0.2.26`, and `git fetch origin && git show --stat origin/chore/cut-v0.2.26` lists the files above.

## Decisions and deviations
- **Amended 2026-10-03 (Owner decision #1103)**: Changelog fragments are collected when the release merges or publishes, never in a release-cut commit. `_plan_changelog_or_exit` and `_write_version_changelog` are not called on the cut path; `CHANGELOG.md` and `changelog.d/` remain byte-identical to the release tip. Dry-run lists fragments present without stating it would collect them. Superseded by [#1450](https://github.com/dan-petty/devops-cli/issues/1450) (the cut collects).
- **Fail-closed error handling**: Eliminated warn-and-continue logic and flag-stripping fallback loops on `gh pr create`. If git push or PR creation fails, exit non-zero immediately.
- **Remote tip version resolution**: `devops release pr` resolves the target version from the checked-out cut branch (derived from the remote release branch tip) rather than the caller's pre-checkout working directory state.
- **Readiness scoping**: The release PR exemption strictly applies to `chore/cut-vX.Y.Z` into the default branch from the same repository. `release/vX.Y.Z` into `main` and `chore/cut-vX.Y.Z` into `release/vX.Y.Z` are no longer exempt and are held to grounding.

## Deliverables
- [x] `src/devops_cli/commands/release.py`: Added `cut_release` shared function and `_update_uv_lock_version`, updated `release_prepare` and `release_pr`, removed `--push/--no-push` option from `release_pr`, removed `_build_pr_fallback_cmd`, `_strip_pr_cmd_flag`, and `_checkout_release_branch`.
- [x] `src/devops_cli/commands/pr.py`: Updated `_is_release_pr` and `_is_release_process_pr` to reflect `chore/cut-vX.Y.Z` into default branch and restrict process PRs.
- [x] `src/devops_cli/config/constants.py`: Updated `CONST_RELEASE_PROCESS_BRANCH_RE`, added `CONST_RELEASE_CUT_BRANCH_RE`, updated doc comments.
- [x] `.github/labels.yml`: Declared `release` label.
- [x] Documentation & convention alignments: `AGENTS.md`, `RELEASE_CYCLE.md`, `docs/agent/tasks/README.md`, `docs/ROUTINE_TASKS.md`, `docs/commands/release.md`, `docs/CLI_REFERENCE.md`.
- [x] Test suites: Updated `tests/test_release.py`, `tests/test_pr_cmd.py`, and `tests/test_github_labels.py`.
- [x] Changelog fragment: `changelog.d/982.md`.
