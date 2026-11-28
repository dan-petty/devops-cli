# Tasks

## 1. Read the full watch list in advisories and sweep

Kind: behavior.

Reads: `src/devops_cli/research/advisories.py`, `src/devops_cli/research/sweep.py`, `src/devops_cli/commands/research.py`, `tests/research/test_advisories.py`, `tests/research/test_sweep.py`, `tests/commands/test_research_advisories.py`.

Changes: `src/devops_cli/research/advisories.py`, `src/devops_cli/research/sweep.py`, `src/devops_cli/commands/research.py`, `tests/research/test_advisories.py`, `tests/research/test_sweep.py`, `tests/commands/test_research_advisories.py`.

- [x] 1.1 Write failing tests in `tests/research/test_advisories.py`, `tests/research/test_sweep.py`, and `tests/commands/test_research_advisories.py` verifying OSV planning and `get_vulnerability` with mapped `osv_ecosystem`/`osv_name`, preserved GitHub watch queries, unpinned handling, `mapped_inventory` in `devops research advisories`, and watch-list + `mapped_inventory` handling in `devops research sweep` and `--dry-run`.
  - Verification: `$ uv run devops ci test tests/research/test_advisories.py tests/research/test_sweep.py tests/commands/test_research_advisories.py`
- [x] 1.2 Implement mapped OSV planning and `key[0]` record lookup in `src/devops_cli/research/advisories.py`, add `watch` to `sweep_dry_run` in `src/devops_cli/research/sweep.py`, and switch `advisories` and `sweep` in `src/devops_cli/commands/research.py` to `mapped_inventory` and `read_watch_list`.
  - Verification: `$ uv run devops ci test tests/research/test_advisories.py tests/research/test_sweep.py tests/commands/test_research_advisories.py`

Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
