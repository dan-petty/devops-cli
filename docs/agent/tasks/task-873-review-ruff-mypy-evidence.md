# Task: ruff and mypy run as review evidence with the project's settings (#873)

**Issue**: [#873](https://github.com/dan-petty/devops-cli/issues/873)
**Feasibility**: Verified that Ruff outputs standard SARIF 2.1.0 with project pyproject.toml settings, mypy validates environment via uv.lock hash against checkout root, and McCabe complexity deltas calculate before/after per function via AST.
**Status**: Done
**Milestone**: v0.2.33
**Priority**: priority/p1-high
**Scope**: scope/review

## Description
Ruff and mypy run as review evidence during code reviews using the project's settings (`pyproject.toml`, `mypy.ini`). Ruff executes under `--output-format sarif` and advisory rules report on diff hunks for branch and PR reviews (or grouped per rule/file on path reviews). mypy runs with environment verification by validating `uv.lock`'s SHA-256 against the main worktree root and isolating cache directories with `python -I`. Changed Python functions show before/after McCabe cyclomatic complexity (`ruff C901`) with configurable threshold flags in `.devops/review.toml`.

## Key Changes
- **Ruff Scanner** (`src/devops_cli/security/ruff.py`): Invokes `ruff check --output-format sarif`, parses SARIF findings into `SecurityFinding`, and filters advisory rules against diff hunks on branches/PRs or groups by file/rule on path reviews.
- **Mypy Scanner** (`src/devops_cli/security/mypy.py`): Checks `uv.lock` integrity matching the checkout worktree, invokes `mypy` with a temporary cache directory and isolated flags, and parses type errors while discarding auxiliary `note:` lines.
- **Complexity Deltas** (`src/devops_cli/security/complexity.py`): Computes before and after McCabe cyclomatic complexity deltas for functions modified in git diffs using AST parsing.
- **Review Pipeline Integration** (`src/devops_cli/ai/review/pipeline.py`): Adds Ruff and mypy to static analyzer buckets, records complexity deltas in markdown reports and session JSON payloads, and validates tool availability.
- **Review Schema** (`src/devops_cli/ai/review_schema.py`): Adds `complexity_delta` field to `ReviewSessionPayload`.
- **Tests** (`tests/test_review_ruff_mypy_evidence.py`, `tests/test_review_static_analyzers.py`): Comprehensive unit and integration tests for scanner execution, advisory diff filtering, mypy uv.lock validation, complexity delta calculation, and report generation.

## Acceptance Criteria
- [x] **Ruff review evidence**: Ruff runs with project settings, emitting SARIF findings into review evidence.
- [x] **Advisory rules reporting**: Advisory rules report on diff hunks on PR/branch reviews and grouped by rule/file on path reviews.
- [x] **Mypy review evidence**: Mypy runs with checkout environment validation (`uv.lock` SHA-256 match), isolating cache and ignoring `note:` continuation lines.
- [x] **Complexity before/after**: Functions modified in git diff report cyclomatic complexity before and after with delta calculations.
- [x] **Markdown report & session JSON**: `review.md` includes complexity delta table and `session.json` records `complexity_delta`.
- [x] **Quality gates & tests**: All unit tests pass cleanly with $M \le 10$ cyclomatic complexity and $\le 5$ nesting depth.
- Pending a person: `uv run devops ci` on the delivering tree, which the orchestrating session runs.
