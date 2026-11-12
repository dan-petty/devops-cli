# Tasks

## 1. The constants gate reads a literal with digit separators and no new value

Kind: fix. Changes: `tests/roadmap/stage/test_roadmap_stage_constants.py`, `src/devops_cli/roadmap/stage/stage_constants.py`.

- [x] 1.1 Write the tests first: a quote of `CONST_AGENTS_MD_MAX_CHARS: Final[int] = 6_500` with the staged value 6500 gives no problem, `= 6_400` gives one problem that says 6400, and "Raise `SUMMARY_MAX_CHARS` to 80" and "The test patches `SUMMARY_MAX_CHARS` to 1" give no problem. Remove the `set-to` case. The four texts fail on `origin/main`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py`
- [x] 1.2 Change `_CANDIDATE_NUMBER` to `(\d+(?:_\d+)*)` with `(?![\d_]|[/.]\w|-\d)`, and remove `to` from `_VALUE_LINK`.
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.3 Verify that the replay gives the same result on the base and on the change.
  - Verification: `$ uv run devops roadmap eval stage --replay`
