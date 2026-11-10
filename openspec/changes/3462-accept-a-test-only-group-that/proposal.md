# Proposal

## Why

Issue #3462: the rule that landed with #3433 refuses a valid `other` group that changes only a test helper or a fixture, so a planner cannot plan a helper-only group. The rule must accept that group and keep the refusal for a group that changes only test modules and names no test function.

## What Changes

- `src/devops_cli/roadmap/stage/stage_change.py` judges only an `other` group whose every changed path is a test module under `tests/`, so a group that changes a test helper is accepted.
- `src/devops_cli/roadmap/stage/stage_paths.py` publishes its existing `_is_test_module` predicate as `is_test_module`, and its three call sites in that module use the new name.
- `tests/roadmap/stage/test_roadmap_stage_content.py` gains the case of a helper group, the case of a path-only refusal and a self-acceptance case with a name of its own.
- The change carries a spec delta on `roadmap-stage`, because the plan check is behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A test-only other group names its test function

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_content.py`

## Feasibility

- The probe confirms the helper path that the issue cites: The path `tests/support/builders.py` is a file of the staging commit.
- The probe moves the test path that the issue cites: The path `tests/roadmap/test_roadmap_stage_content.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_content.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The probe moves the source path the same way: The path `src/devops_cli/roadmap/stage_change.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_change.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The rule of #3433 is in the staged tree, so this change narrows it: `search_code` for `_test_only_group_problems` returned `src/devops_cli/roadmap/stage/stage_change.py:1457:def _test_only_group_problems(proposal: StageProposal) -> list[str]:` and `src/devops_cli/roadmap/stage/stage_change.py:1675:problems.extend(_test_only_group_problems(proposal))`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed the condition that the plan changes: `src/devops_cli/roadmap/stage/stage_change.py:1466:p.startswith("tests/")`.
- `read_file` of the same file showed that a code span that holds only a path stays refused: `src/devops_cli/roadmap/stage/stage_change.py:1453:segment = span.strip().rsplit("::", 1)[-1]`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed the one predicate that decides the test-module form: `src/devops_cli/roadmap/stage/stage_paths.py:def _is_test_module`, with three call sites in that module.
- The constants that the plan relies on have these staged values: `src/devops_cli/roadmap/stage/stage_paths.py:75:_TESTS_TOP: Final[str] = "tests/"`; `src/devops_cli/roadmap/stage/stage_paths.py:78:_TEST_MODULE_PATTERNS: Final[tuple[str, ...]] = ("test_*.py", "*_test.py")` holds the two pytest patterns; and `src/devops_cli/roadmap/stage/stage_change.py:200:_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"` names the file whose change needs the self-acceptance test.
- `src/devops_cli/roadmap/stage/stage_change.py:255:STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (` holds `src/devops_cli/roadmap/stage/stage_change.py` and `src/devops_cli/roadmap/stage/stage_paths.py`, so the plan runs the replay; `src/devops_cli/roadmap/stage/stage_change.py:264:STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"` gives the command of the score task; and `src/devops_cli/roadmap/stage/stage_change.py:272:_FAILS_ON_BASE: Final[str] = "fails on the base"` gives the phrase that the gate test holds.
- The existing cases that the plan keeps: `tests/roadmap/stage/test_roadmap_stage_content.py:765:def test_a_test_only_other_group_with_no_named_test_is_refused() -> None:` is the conditional case, and `tests/roadmap/stage/test_roadmap_stage_content.py:853:def test_content_problems_accepts_this_plans_own_proposal() -> None:` already builds the #3266 plan's own proposal, so the new self-acceptance case takes a name of its own.
- The plan answers the reported fault: no What Changes item names a fixture folder, because the rule drops that exclusion and judges every group path by the two pytest patterns alone.
- `_test_only_group_problems` and `is_test_module` are pure functions of a proposal and of a path, so neither call needs a checkout of the repository, a client of a service or a network.
- The two verify commands `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` and `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py` run `uv`, `devops` and `pytest`, each a runner tool of the image, and they need no network; the pod runs as a non-root user with a read-only root filesystem, so pytest writes its temporary files under `/tmp`.
- The replay command `uv run devops roadmap eval stage --replay` needs a checkout of the repository at the base commit and at the change, because it replays the recorded golden cases against the staged tree.

## Existing Tool Considered

No open, maintained tool covers the need: the rule compares the free text of one stage plan with the paths that a group changes, and no linter, schema or test framework checks that. The change builds its own rule at a cost of about 20k tokens to build, 10k tokens to keep and about 2 hours of elapsed time. It deletes no internal code; it narrows `_test_only_group_problems` and renames the existing `_is_test_module` predicate to `is_test_module`.

## Dependencies

- #4425 changes `.github/workflows/ci.yml`, a path that the issue names as an example of a file outside the test tree; this plan changes no path of that pull request and does not wait for it.
