# Task: Make Roadmap Refine Dry-Run Request-Free (#1867)

**Issue**: [#1867](https://github.com/dan-petty/devops-cli/issues/1867)
**Scope**: scope/roadmap
**Feasibility**: Verified that `devops roadmap refine --dry-run` previously opened the roadmap store and planned refinements unconditionally, invoking GitHub GraphQL queries and LLM model calls before skipping the write phase. Investigated existing dry-run patterns across roadmap commands (`reprioritize`, `migrate`, `render`, `close`, `intake`). Added `refine_requests` to `src/devops_cli/roadmap/request_plan.py` to construct planned requests for reads and writes. Added `dry_run_refine` returning `RefinePlan(dry_run=True, ...)` to `src/devops_cli/roadmap/refine.py`. Updated `refine_cmd` in `src/devops_cli/commands/roadmap.py` to short-circuit early on `dry_run or is_dry_run()` and render the plan without opening the store or invoking LLM/search. Verified with socket, process, and LLM call guards in `tests/test_roadmap_dry_runs.py`.

## Description
The `devops roadmap refine --dry-run` command previously executed `_open_roadmap` and `plan_refine` unconditionally, consuming GraphQL rate limits and calling LLM inference during dry runs. Under the project invariants, a dry-run command must make zero external network requests, start no processes, and make no model calls, returning the typed result marked as a dry run with placeholders.

- In `src/devops_cli/roadmap/request_plan.py`:
  - Added `write_issue_body` helper to `StoreRequests` to represent the issue body edit GraphQL/REST request.
  - Implemented `refine_requests(repo, ref, *, item=None, limit=None)` returning the planned reads and writes for roadmap refinement, handling both whole-board and single-item modes.
  - Exported `refine_requests`.
- In `src/devops_cli/roadmap/refine.py`:
  - Extended `RefinePlan` with `dry_run: bool = False`, `requests: tuple[PlannedRequest, ...] = ()`, and `write_requests: tuple[PlannedRequest, ...] = ()`, with default empty strings for `sha` and `branch`.
  - Implemented `dry_run_refine(repo, *, ref=None, item=None, limit=None) -> RefinePlan`.
  - Exported `dry_run_refine`.
- In `src/devops_cli/commands/roadmap.py`:
  - In `refine_cmd`, intercepted `dry_run or is_dry_run()` immediately after resolving `target_repo`, calling `dry_run_refine` and `render_dry_run` and returning early.
- In `tests/test_roadmap_dry_runs.py`:
  - Added `"refine"` to `JOBS`.
  - Added monkeypatches in `no_requests` fixture to fail immediately if `get_llm_client` or `tavily_search` is called.
  - Added `"refine"` to `test_an_exported_dry_run_wins_over_confirm`.
  - Updated `test_each_dry_run_returns_its_jobs_result_type_marked_as_a_dry_run` to verify `RefinePlan`.
  - Included `refine_requests` in `test_no_roadmap_plan_lists_a_board_command_gh_resolves_by_reading_the_board_first`.
  - Added `test_refine_dry_run_with_item_makes_no_requests`.
- In `tests/test_roadmap_refine.py`:
  - Updated `test_the_cli_exits_1_after_reporting_a_failed_item` parameterization to `["--confirm", None]`, as `--dry-run` now safely short-circuits without model execution.

## Acceptance Criteria
- [x] `devops roadmap refine --dry-run` makes no GitHub request and no model call.
- [x] Tests fail if the command makes either a GitHub call or a model call.
- [x] The same test pattern in `tests/test_roadmap_dry_runs.py` covers `refine` alongside other roadmap jobs (`reprioritize`, `migrate`, `render`, `intake`, `close`).
- [x] Full `devops ci` quality gate passes with 100% passing status.
