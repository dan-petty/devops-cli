# Task: Full Gate Runs Once Per Push With Pre-Push Verdict Reuse (#1663)

**Issue**: [#1663](https://github.com/dan-petty/devops-cli/issues/1663)
**Scope**: scope/ci
**Feasibility**: CI cache analysis confirmed that `devops ci` verdicts are keyed on repository content (worktree blob hashes of tracked and untracked files, config files, and options), making verdicts invariant across `git add` and `git commit`. A matching verdict allows the pre-push hook to complete in 9s–14s instead of repeating a full 200s–930s quality gate. Updating instructions in `AGENTS.md` and `docs/SDLC.md` establishes that the pre-push hook's run is the gate run and guides developers and agents to run manual gates only after the final rebase or amend.

| Operation | Before | After |
|---|---|---|
| Pre-push check with matching verdict | 200s – 930s (full re-run) | 8.7s – 13.8s (cache hit) |
| Post-amend file change | Uncached (requires new run) | Invalidated as expected |

## Description

- [x] Added `test_verdict_survives_add_and_commit_but_misses_after_amend` to `tests/test_ci_cache.py` demonstrating that a saved CI verdict is preserved across `git add` and `git commit` of a tree, and invalidated after an amend that changes a file.
- [x] Updated `AGENTS.md` to specify that the pre-push hook's `uv run devops ci` is the gate run, manual runs count only when nothing changes prior to push, and doc rewrites must be committed rather than pushed unchanged.
- [x] Updated `docs/SDLC.md` with identical pre-push gate guidance.
- [x] Verified `uv run devops docs check` passes with 100% freshness.
- [x] Authored changelog fragment `changelog.d/1663.md` under `### Changed`.
- [x] Verified full quality gate passes via `uv run devops ci`.
