# Design

## Decisions

### Expand `test-shard` in `.github/workflows/ci.yml` from five to six shards and refresh `tests/module_durations.json`

Refresh `tests/module_durations.json` with `uv run devops ci durations` across the last 20 `main` push runs (1,436 modules) so newly added test files have measured weights, and extend `.github/workflows/ci.yml` (`jobs.test-shard.strategy.matrix.shard`) to `[1, 2, 3, 4, 5, 6]` matching `docs/TESTING.md:207` ("write the record again first, then add a number to the matrix of the job `test-shard`"). Update `docs/TESTING.md`, `docs/SDLC.md`, and `tests/commands/test_ci_shard.py` cleanly.

## Rejected alternatives

- **Raise the 360 s limit or skip tests**: `AGENTS.md` rule 5 and `docs/TESTING.md:205` forbid lowering the quality limit or dropping needed tests.
- **Replace `shard_test_files` with `pytest-split`**: `pytest-split` runs collection on every file in every worker and does not read GitHub Actions `coverage-shard-*` JUnit artifacts or integrate with `devops ci durations`.
- **Keep five shards after only refreshing `tests/module_durations.json`**: Even after `ed2e4240b` refreshed durations on `main`, `uv run devops ci job-time --job "Tests & Coverage"` shows a 20-run mean of 351 s with recent runs still taking 340–391 s, leaving only a 9 s margin below 360 s; adding a sixth shard reduces per-shard execution time well under 360 s.
