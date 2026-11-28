## ADDED Requirements

### Requirement: CI test row runs six balanced shards
`.github/workflows/ci.yml` (`test-shard`), `docs/TESTING.md`, and `docs/SDLC.md` SHALL configure and document six test shards (`shard: [1, 2, 3, 4, 5, 6]`), weighted by `tests/module_durations.json`, and `shard_test_files` SHALL partition every module of `tests/` into six non-empty shards.

#### Scenario: Six shards cover every test module once and workflow checks pass
- **WHEN** `uv run devops ci test tests/commands/test_ci_shard.py` runs `test_the_shards_cover_every_test_module_once[6]`, `uv run devops ci --check --only actionlint,zizmor,docs` validates `.github/workflows/ci.yml` and docs, and `uv run devops ci durations` refreshes `tests/module_durations.json`
- **THEN** all six shards are non-empty and disjoint, `actionlint`, `zizmor`, and `docs` exit 0, and `tests/module_durations.json` holds current timings from the last 20 `main` runs
