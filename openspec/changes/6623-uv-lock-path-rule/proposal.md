# Proposal: #6623

## Why
#6623: `fix-conflict` stops almost every conflict in `uv.lock` before tier 1 runs. `release_conflict` gives the side of the pull request of each conflicted path to `is_release_path`, which stops any path whose diff holds a `version =` line. Each package block of `uv.lock` has such a line, so the round stops with "Conflict on a release path", and `uv lock` does not run. The owner decided on 2026-11-21 to make the guard a path rule.

## What Changes
- `is_release_path` checks the version line only in `pyproject.toml`. `CHANGELOG.md` and the files of release-please stay release paths.
- The `__version__` check of other files goes: release-please writes the version into `pyproject.toml` and `uv.lock`, and no file under `src/` sets `__version__`.
- `uv.lock` is a lock path: tier 1 takes the side of the default branch (`checkout --ours` and `add`, or `git rm` when main has no file) and runs `uv lock` again. The plan and the round use the same rule (`release_conflict`).
- The change is observable (the result of a round), so the spec `roadmap-fix-conflict` gets a delta.

## Capabilities
- `roadmap-fix-conflict`: the requirement of the release path names the paths, and a new scenario settles the version line of a package in `uv.lock`.

## Impact
- A bot pull request whose `uv.lock` conflicts on a package version gets a tier 1 round in place of a stop.
- A conflict on the version line of `pyproject.toml` still stops.
- A conflict on another file stops as before, as a conflict that tier 1 cannot settle.
- The change fits one pull request.

## Feasibility
- `src/devops_cli/roadmap/steps/fix_conflict.py`: `resolve_tier1` already takes the default branch for `uv.lock` and runs `uv lock` (`_regenerate_lock_and_commit`). Only `is_release_path` stops the round first.
- The evidence of #6623: a probe on #6620 with a `uv.lock` package at 1.0.0, 1.1.0 on the branch and 1.2.0 on main stopped with no `uv` call. The new test with the same lines failed on the old rule and passes on the new rule.

## Existing Tool Considered
- `uv lock` (astral-sh/uv), which tier 1 already runs, makes the lock again from `pyproject.toml`. No tool classifies release paths, so the rule stays a short function of the step.
- Deleted internal code: the `version =` check of each path but `pyproject.toml`, and the `__version__` check.
