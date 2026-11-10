# Proposal

## Why

Issue #3414: the stage plan validation checks that each path a plan names exists at the staged commit, and it never checks that the plan names the existing test that the change will break. A plan can name only the test it creates and pass every stage check, and the implement job then meets the failing existing test with no name for it in the plan.

## What Changes

- `src/devops_cli/roadmap/stage/stage_paths.py` records the existing tests of each module that a behavior group changes, and refuses a group that names none of them.
- `src/devops_cli/lang/en/messages.py` gains the message of the new problem.
- `src/devops_cli/roadmap/stage/stage_change.py` gives the `paths` gate the record when the caller passes it.
- `src/devops_cli/roadmap/stage/stage_request.py` and `src/devops_cli/roadmap/stage/stage.py` carry the record to the gates of the job.
- `src/devops_cli/roadmap/plan_recheck.py` carries the record to the gates of the merged plan.
- `docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md` state the rule.
- The change carries a spec delta because the stage job and its plan check are behavior that a consumer observes: five requirements join `roadmap-stage`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: Refuse a behavior group that omits the test of its module, Accept a behavior group that names the test of its module, Exempt a module that has no existing test, Leave out the test files that the plan creates, Report one problem for each group that omits its test

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/plan_recheck.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_module_tests.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`, `tests/roadmap/test_roadmap_plan_recheck.py`

## Feasibility

- The premise holds at the staged paths, and the probe answers word for word: The path `tests/roadmap/test_roadmap_implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_step.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The probe moves the source path the same way: The path `src/devops_cli/roadmap/implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/support/implement_step.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.
- The probe keeps the third path of the issue: The path `src/devops_cli/roadmap/step_files.py` is a file of the staging commit. The fourth path of the issue is no file either, and `list_files` of `src/devops_cli/roadmap/stage` listed `stage_paths.py` in that folder, so the rule goes in `src/devops_cli/roadmap/stage/stage_paths.py`.
- The defect of the issue holds at the staged commit: `search_code` for `roadmap.step_files` gave `tests/roadmap/implement/test_roadmap_implement_step.py:61:from devops_cli.roadmap.step_files import parse_task_groups`, and `search_code` for `The first group (#1)` gave `tests/roadmap/implement/test_roadmap_implement_step.py:284:"chore: The first group (#1)",`. So a plan that changes `src/devops_cli/roadmap/step_files.py` and names no `tests/roadmap/implement/test_roadmap_implement_step.py` passes every stage check today.
- The path check has no such rule: `read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed `src/devops_cli/roadmap/stage/stage_paths.py:356:def path_problems(`, which reports a named path that the tree lacks and that no group creates, and it never reads the test of a group.
- The rule joins the `paths` gate: `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:1890:def check_gates(` with `src/devops_cli/roadmap/stage/stage_change.py:1927:*path_problems(proposal.groups, tree, manifest_references, change=change),`.
- The record has a model in the staged tree: `read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed `src/devops_cli/roadmap/stage/stage_paths.py:310:def record_test_references(` with `src/devops_cli/roadmap/stage/stage_paths.py:66:_TESTS_TOP: Final[str] = "tests/"` and `src/devops_cli/roadmap/stage/stage_paths.py:69:_TEST_MODULE_PATTERNS: Final[tuple[str, ...]] = ("test_*.py", "*_test.py")`.
- The constants that the plan relies on are staged as they are read: `src/devops_cli/roadmap/stage/stage_change.py:267:GATE_DEFECT_PATHS: Final[tuple[str, ...]] = (` holds `src/devops_cli/roadmap/stage/stage_change.py`; `src/devops_cli/roadmap/stage/stage_change.py:271:_FAILS_ON_BASE: Final[str] = "fails on the base"` gives the phrase that the test task holds; `src/devops_cli/roadmap/stage/stage_change.py:199:_PLAN_CHECK_FILE: Final[str] = "src/devops_cli/roadmap/stage/stage_change.py"` names the file whose change needs the self-acceptance test; `src/devops_cli/roadmap/stage/stage_change.py:254:STAGE_EVAL_TRIGGER_PATHS: Final[tuple[str, ...]] = (` holds `src/devops_cli/roadmap/stage/stage_paths.py`; and `src/devops_cli/roadmap/stage/stage_change.py:263:STAGE_EVAL_REPLAY: Final[str] = "uv run devops roadmap eval stage --replay"` gives the command of the score task.
- The job carries the record through one keyword: `read_file` of `src/devops_cli/roadmap/stage/stage_request.py` showed `src/devops_cli/roadmap/stage/stage_request.py:65:def gate_arguments(`, and `read_file` of `src/devops_cli/roadmap/stage/stage.py` showed `src/devops_cli/roadmap/stage/stage.py:1557:manifest_references = (` built from `self._grep` beside it.
- The recheck passes the same record: `read_file` of `src/devops_cli/roadmap/plan_recheck.py` showed `src/devops_cli/roadmap/plan_recheck.py:345:manifest_references=record_test_references(proposal.groups, shared.test_search),`.
- The plan answers the problem of the earlier reply: group 2's test task quotes the omitted test `tests/roadmap/implement/test_roadmap_implement_step.py`, states that it `fails on the base`, and holds `StageProposal`, `content_problems` and `no problem`, as `_gate_defect_problems` and `_self_acceptance_problems` ask. It cites the moved locations of the issue and no path that this run did not show.
- `record_module_tests` takes the search callable as its argument, and its precondition is a checkout of the repository at the staged commit, because the search of the job runs `git grep` there.
- `existing_test_problems` is a pure function of the groups, the tree and the record: it needs no checkout, no client and no network.
- `gate_arguments` is a pure function of the request and the record: it needs no checkout, no client and no network.
- The recheck's call needs a checkout of the repository at the ref that the pass reads, which `shared.test_search` searches.
- The plan introduces no program: `uv run devops ci test` runs `devops` and `pytest` of the runner image, `uv run devops ci docs` runs `devops`, and `uv run devops roadmap eval stage --replay` runs `devops` over a checkout of the repository.
- A failing `uv run devops ci test` is the failure class `test` and a failing `uv run devops ci docs` is `lint`; both take the action repair, and the pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false` and `seccompProfile: RuntimeDefault`.
- The first check against the real system is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_tests.py`, then `uv run devops roadmap eval stage --replay` with the score before and after the change, then `uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py`.
- The issue can be built as written in its new locations: the check it asks for has its home in `src/devops_cli/roadmap/stage/stage_paths.py`, and the plan changes no code to compensate for the paths that commit bff2f14fd moved.

## Existing Tool Considered

No open, maintained tool or library covers this rule: it reads the `src/` layout and the `tests/` naming convention of this repository and runs inside the stage job with no test suite. The change builds its own check at a written cost of about 6,000 tokens to build, keep and fix it, and about 1 hour of elapsed time, and it deletes no internal code.

## Dependencies

None.
