# Proposal

## Why

The stage golden set test pins its case counts with literals, so a plan that adds a case must edit the test, and no prompt or gate reminds the planner (#3445). The plan of #3436 for #3411 left that edit out, and the count test would have failed. The test now derives the counts from the fixtures and keeps one intended reviewed pull set, so a new case needs one edit.

## What Changes

- Derive the case counts of the stage golden set in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` from the loaded cases and `EVALUATED_PULLS`, and delete the literals 54, 5 and 49.
- Add the module-level helper `check_case_counts`, which compares the reviewed pulls with the intended set, names each missing pull, and computes the total as `len(intended) + len(good)`.
- Rename `test_the_set_holds_the_49_plans_and_five_good_ones` to `test_the_set_holds_the_reviewed_plans_and_the_good_ones`, so the test name states no count.
- Add `test_one_more_case_is_accepted_when_the_intended_set_holds_its_pull`, which copies the cases to `tmp_path`, adds a reviewed case with a new pull, and calls `check_case_counts`.
- The change edits one test module and no product code, so it carries no spec delta: the living specs of the stage eval stay as they are.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`

## Weakened checks

- **`tests/roadmap/stage/test_roadmap_stage_eval_cases.py::test_the_set_holds_the_49_plans_and_five_good_ones`**: Stopped: a test name and assertions that pin the stage golden set size to literal 49 and 5. Safeguard: `check_case_counts` derives the counts from fixtures and `tests/roadmap/stage/test_roadmap_stage_eval_cases.py::test_the_set_holds_the_reviewed_plans_and_the_good_ones` asserts them.

## Feasibility

- The issue cites `tests/roadmap/test_roadmap_stage_eval_cases.py`, and the probe shows that the path moved: "The path `tests/roadmap/test_roadmap_stage_eval_cases.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it." The plan changes the staged path and creates no file at the old one.
- The issue also cites `tests/roadmap/test_roadmap_stage_eval_run.py`, and the probe shows that the path moved too: "The path `tests/roadmap/test_roadmap_stage_eval_run.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_eval_run.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it."
- The literals of the issue (42, 3 and 39) are stale, and the premise still holds at the staged path: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:63:assert (frozenset(reviewed), len(cases), len(good)) == (EVALUATED_PULLS, 54, 5)` and `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:64:assert len(EVALUATED_PULLS) == 49`.
- The test name states the count as well: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py:def test_the_set_holds_the_49_plans_and_five_good_ones`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` showed the count test at line 59, the intended set `EVALUATED_PULLS` at line 44, and the two literal assertions at lines 63 and 64.
- `search_code` with `EVALUATED_PULLS` returned only `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` lines 44, 63 and 64 and one archived task, so the intended reviewed set lives in one module.
- `references` with `EVALUATED_PULLS` returned 2 files and 4 lines: the test module at lines 44, 63 and 64, and `openspec/changes/archive/2026-11-05-3411-refuse-a-what-changes-item-that/tasks.md` at line 23, which is under `openspec/changes/archive/` and needs no change.
- `references` with `test_the_set_holds_the_49_plans_and_five_good_ones` returned 1 file and 1 line, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` at line 59, so the rename touches one place and no selection manifest.
- `search_code` with `len(cases)` returned no other test that pins the size of the stage set; `read_file` of `tests/invariants/test_roadmap_eval_fixtures.py` showed the implement set guarded by `len(cases) >= 10`, not the stage set.
- `list_files` of `tests/fixtures/roadmap_eval/stage` listed 54 case folders: 49 reviewed cases and 5 folders with the `good-` prefix, which matches the assertions at lines 63 and 64.
- The new guard covers those 49 reviewed pulls and 5 good cases. Each of the 49 pulls stays in `EVALUATED_PULLS` and is allowlisted with a reason: it is a reviewed case of the golden set, and the guard removes or restricts none of them, so no follow-up issue is needed for the rest.
- `shutil.copytree` reads `REPO_ROOT / CASES_DIRECTORY`, so it needs a checkout of the repository; the test needs no client and no network.
- `load_cases` receives `tmp_path / "stage"`, so it reads no checkout, no client and no network; `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` showed `load_cases` at line 249 takes the case directory and `CASES_DIRECTORY` at line 70 holds `tests/fixtures/roadmap_eval/stage`.
- The first check of the implementation is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, which runs the derived count, the reviewed-set guard and the new temporary-set test offline.
- The issue asks for no prompt and no gate change, and the plan makes none: the change stays in the one test module.

## Existing Tool Considered

No open tool or library covers this need: the change edits one pytest module over the fixtures and deletes no product code. The written cost is 300 tokens to build, keep and fix, and 10 minutes. It deletes no internal code.

## Dependencies

None.
