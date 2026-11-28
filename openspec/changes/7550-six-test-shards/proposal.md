# Proposal: #7550

## Why

In #7550, `devops ci job-time` reported that the last 20 runs of `Tests & Coverage` on `main` averaged 367 s, over the 360 s limit of `AGENTS.md` rule 5 (300 s + 60 s tolerance), with individual shard runs hitting up to 399–420 s. Per `docs/TESTING.md:207`, when `Test Job Duration` nears the bound, the remedy is refreshing `tests/module_durations.json` from recent shard reports (`devops ci durations`) and adding a sixth shard to `test-shard` in `.github/workflows/ci.yml`.

## What Changes

- Refresh `tests/module_durations.json` from the JUnit reports of the last 20 `main` CI runs via `uv run devops ci durations` (1,436 test modules recorded).
- Expand `test-shard` in `.github/workflows/ci.yml` from 5 shards to 6 (`shard: [1, 2, 3, 4, 5, 6]`).
- Update `docs/TESTING.md` and `docs/SDLC.md` to document six test shards (`--shards 6`, one sixth of recorded test time per shard).
- Add the `6`-shard case to `test_the_shards_cover_every_test_module_once` in `tests/commands/test_ci_shard.py`.
- Add a requirement in `specs/ci-test-shards/spec.md` for the six-shard CI split and workflow matrix.

## Capabilities

### Modified Capabilities

- `ci-test-shards`: Documents and verifies six shards in `.github/workflows/ci.yml`, `tests/module_durations.json`, `docs/TESTING.md`, `docs/SDLC.md`, and `tests/commands/test_ci_shard.py`.

## Impact

- Workflow: `.github/workflows/ci.yml` (`test-shard` matrix).
- Data & Tests: `tests/module_durations.json`, `tests/commands/test_ci_shard.py`.
- Docs: `docs/TESTING.md`, `docs/SDLC.md`.
- Fits in one pull request.

## Feasibility

- Ran `uv run devops ci durations`: wrote mean seconds of 1,436 test modules from 20 ended `main` runs to `tests/module_durations.json`.
- `shard_test_files` (`src/devops_cli/core/test_selection.py:356`) already supports arbitrary `shards >= 1`, and `.github/workflows/service-image-test.yml:116` already runs `shard: [1, 2, 3, 4, 5, 6]`.

## Existing Tool Considered

Uses the repository's existing `devops ci durations` and `shard_test_files` balance splitter (`pytest-split` lacks CI JUnit artifact collection and per-test skip-reason summaries required by `openspec/specs/ci-test-shards/spec.md`). No custom code is built and no internal code is deleted.
