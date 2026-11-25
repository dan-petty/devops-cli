# Tasks

## 1. Rename roadmap-stage-eval-commits to roadmap-eval-commits and add failing golden-set tests

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_eval.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `tests/gate/roadmap_stage_eval_commits.py`, `tests/invariants/test_roadmap_stage_eval_commits_check.py`, `tests/invariants/test_roadmap_eval_fixtures.py`, `tests/commands/test_ci_gate_rows.py`, `docs/TESTING.md`, `.github/workflows/ci.yml`. Changes: `tests/invariants/test_roadmap_eval_fixtures.py`, `tests/invariants/test_roadmap_eval_commits_check.py` (replaces `tests/invariants/test_roadmap_stage_eval_commits_check.py`), `tests/commands/test_ci_gate_rows.py`, `tests/gate/roadmap_eval_commits.py` (replaces `tests/gate/roadmap_stage_eval_commits.py`), `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/module_durations.json`, `.github/workflows/ci.yml`, `docs/TESTING.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `docs/MCP_TOOLS.md`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

- [x] 1.1 Write failing tests first: update `tests/invariants/test_roadmap_eval_fixtures.py` (`MAX_BYTES = 1_000_000`, assert `len(cases) >= 40`, and add `test_the_scope_counts_match_the_delivery_mix` checking the 90-day scope counts), replace `tests/invariants/test_roadmap_stage_eval_commits_check.py` with `tests/invariants/test_roadmap_eval_commits_check.py` covering both stage `StageCase` and implement `LoadedCase` commits, and update `tests/commands/test_ci_gate_rows.py` for `"roadmap-eval-commits": "roadmap_eval_commits"`
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_eval_fixtures.py tests/invariants/test_roadmap_eval_commits_check.py tests/commands/test_ci_gate_rows.py` fails on the base
- [x] 1.2 Replace `tests/gate/roadmap_stage_eval_commits.py` with `tests/gate/roadmap_eval_commits.py` (`_ROW = "roadmap-eval-commits"` reading both stage cases and `implement_eval.load_cases`), update `src/devops_cli/commands/ci.py` and `src/devops_cli/lang/en/messages.py` for `roadmap-eval-commits`, update `.github/workflows/ci.yml`, `docs/TESTING.md`, and `tests/module_durations.json`, and regenerate docs and MCP tool listing snapshot
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_eval_commits_check.py tests/commands/test_ci_gate_rows.py` passes

## 2. Add 67 implement golden cases across the 90-day delivery scopes

Kind: data. Reads: `src/devops_cli/roadmap/implement/implement_eval.py`, `tests/invariants/test_roadmap_eval_fixtures.py`, `tests/roadmap/implement/test_roadmap_implement_eval_harbor.py`, `tests/invariants/test_committed_addresses.py`, `tests/invariants/test_adr_superseded_citations.py`. Changes: `tests/fixtures/roadmap_eval/implement/`.

- [x] 2.1 Write the 67 new fixture folders under `tests/fixtures/roadmap_eval/implement/` (reaching 81 fixtures across 49 scopes) with `case.json` (`base` 40-char parent SHA, `group`, `changes`, `tests_pass`), `issue.md`, and `plan/{proposal,design,tasks}.md` (unticked `[ ]` tasks)
  - Verification: `$ uv run devops ci test tests/invariants/test_roadmap_eval_fixtures.py tests/roadmap/implement/test_roadmap_implement_eval_fixtures.py tests/roadmap/implement/test_roadmap_implement_eval_harbor.py tests/invariants/test_committed_addresses.py tests/invariants/test_adr_superseded_citations.py` passes
- [x] 2.2 Run `roadmap-eval-commits`, `docs`, `openspec`, `constructs`, `lint`, `format`, `typecheck`, `test-tree`, and post the per-scope fixture count comment on issue #5516
  - Verification: `$ uv run devops ci --check --no-cache --only roadmap-eval-commits,test-tree,docs,lint,format,typecheck,openspec,constructs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
