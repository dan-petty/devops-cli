# Proposal: #6380

## Why
A plain `uv run` in a fresh clone or worktree installs `[dependency-groups] dev` without `[project.optional-dependencies] review`. Because `lizard` only lives in `review`, `importlib.util.find_spec("lizard")` returns `None` in `complexity_fact`, skipping `cat-file blob` reads and failing `review_window` git contract and review-facts tests that pass in CI (`uv sync --all-groups --all-extras`).

## What Changes
- Declare `lizard==1.26.1` in `[dependency-groups] dev` in `pyproject.toml` (keeping `review = ["lizard==1.26.1"]` in `[project.optional-dependencies]`).
- Update `uv.lock` if needed cleanly.
- Add `tests/invariants/test_review_extra_present.py` asserting `lizard` is importable and failing with `uv sync --all-extras` when `importlib.util.find_spec("lizard")` returns `None`.
- Register `test_review_extra_present.py` in `docs/TESTING.md`.

## Capabilities
- `review-extra-guard`: ensure plain `uv` test syncs install `lizard` and fail fast with `uv sync --all-extras` if absent.

## Impact
Every local clone, worktree, devcontainer, and CI runner gets `lizard` via `uv sync` without `--extra review`. Production `--no-dev` Docker builds continue installing `--extra review`.

## Feasibility
Confirmed against `pyproject.toml` lines 99 and 104-137, `src/devops_cli/roadmap/project_review/facts.py` lines 221-248, `tests/core/test_git_contract.py`, and `tests/roadmap/project_review/test_review_facts.py`.

## Existing Tool Considered
Alternatives check on #6380 (2026-11-19) recorded `none`; `lizard` is already a repository extra. Written cost of the invariant test guard: about 5k tokens to write, 1k per future adjustment, and 30 minutes elapsed.
