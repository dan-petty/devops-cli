# Proposal: #5516

## Why

The implement golden set (`tests/fixtures/roadmap_eval/implement`) holds 14 fixtures totaling 276,058 bytes across five scopes (`security`: 7, `cli`: 3, `argo`: 2, `k8s`: 1, `telemetry`: 1). E2 and E3 of the pipeline split design (#5482) require 40 or more cases for statistical power, and the existing base-commit gate row `roadmap-stage-eval-commits` reads only `tests/fixtures/roadmap_eval/stage`, leaving implement `base` SHAs unverified (#5516).

## What Changes

- Add 67 golden implement fixtures under `tests/fixtures/roadmap_eval/implement/` from merged delivery pull requests of the last 90 days across all 49 scopes that hold complete three-file OpenSpec archives, bringing the set to 81 cases (at least 1 case per scope and proportional to the 90-day delivery distribution) while staying under 1,000,000 bytes.
- Update `tests/invariants/test_roadmap_eval_fixtures.py` to require at least 40 fixtures (`test_the_set_holds_at_least_forty_fixtures_with_the_items_of_the_baseline`), raise `MAX_BYTES` from `300_000` to `1_000_000`, and add `test_the_scope_counts_match_the_delivery_mix` recording the 90-day delivery distribution and asserting exact scope counts parsed from each fixture `title`.
- Rename the CI gate row `roadmap-stage-eval-commits` to `roadmap-eval-commits`: move `tests/gate/roadmap_stage_eval_commits.py` to `tests/gate/roadmap_eval_commits.py` and extend `bad_base_commits` and `outcome` to check both `StageCase.base_commit` and `LoadedCase.case.base` via `git cat-file -e <sha>^{commit}`; update `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_ci_gate_rows.py`, `.github/workflows/ci.yml`, `docs/TESTING.md`, `tests/module_durations.json`, generated CLI/MCP docs, and the MCP tool listing snapshot.
- Move `tests/invariants/test_roadmap_stage_eval_commits_check.py` to `tests/invariants/test_roadmap_eval_commits_check.py` and test shallow-clone failure, unresolvable stage/implement commits, `NO_COMMIT` without a note, and passing full-hash stage + implement sets with canned answers.
- Update `openspec/specs/ci-gate-rows/spec.md`, `openspec/specs/roadmap-stage-eval/spec.md`, and `openspec/specs/roadmap-eval-implement/spec.md` for the renamed gate row and expanded implement golden set.
- Fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: Rename the `roadmap-stage-eval-commits` requirements to `roadmap-eval-commits` covering both stage and implement golden base commits.
- `roadmap-stage-eval`: Update `Each commit of the set is a real commit or the case reads none` to reference `roadmap-eval-commits`.
- `roadmap-eval-implement`: Update `The committed set holds both good and bad results` and `One Harbor task folder for each implement fixture`, and add requirements `Case content`, `Base commit exists`, `Size bound`, and `Scope counts`.

## Impact

- Fixtures: `tests/fixtures/roadmap_eval/implement/` (67 new fixture folders; 81 total)
- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`
- Gate & Tests: `tests/gate/roadmap_eval_commits.py`, `tests/invariants/test_roadmap_eval_commits_check.py`, `tests/invariants/test_roadmap_eval_fixtures.py`, `tests/commands/test_ci_gate_rows.py`, `tests/module_durations.json`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`
- Documents & Workflows: `docs/TESTING.md`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`, `docs/MCP_TOOLS.md`, `.github/workflows/ci.yml`
- Deleted paths: `tests/gate/roadmap_stage_eval_commits.py`, `tests/invariants/test_roadmap_stage_eval_commits_check.py`

## Feasibility

- Confirmed `tests/fixtures/roadmap_eval/implement` holds 14 fixtures totaling 276,058 bytes (`< MAX_BYTES = 300_000` in `tests/invariants/test_roadmap_eval_fixtures.py:15`) and `tests/invariants/test_roadmap_eval_fixtures.py:28` asserts `len(cases) >= 10`.
- Confirmed `git rev-parse --is-shallow-repository` returns `false` and `tests/gate/roadmap_stage_eval_commits.py:30` only reads `stage_eval_cases.load_cases(REPO_ROOT / CASES_DIRECTORY)` without calling `implement_eval.load_cases`.
- Scanned the last 90 days of `origin/main` (`1,576` merged OpenSpec delivery commits across `49` Conventional Commit scopes); proportional allocation with minimum 1 case per scope produces `81` cases (`67` new + `14` existing) within ~884 KB (`< 1,000,000` bytes), each passing `parse_task_groups`, `weakened_checks`, `recorded_tests`, non-empty `tests_pass`, real GitHub issue text, and zero private addresses or superseded ADR citations.

## Existing Tool Considered

Harbor (`harbor-framework/harbor`) is the open, maintained eval harness already integrated via `devops roadmap eval harbor export` (`docs/commands/roadmap.md`, `docs/TESTING.md`). Harbor executes exported task folders and does not supply repository-specific golden cases, so cases stay in the existing `implement_eval` fixture schema; building a new external harness is avoided (written issue estimate: 300,000 to 500,000 agent tokens and 1 day). Removed internal files: `tests/gate/roadmap_stage_eval_commits.py` and `tests/invariants/test_roadmap_stage_eval_commits_check.py` (renamed to `roadmap_eval_commits.py` and `test_roadmap_eval_commits_check.py`).
