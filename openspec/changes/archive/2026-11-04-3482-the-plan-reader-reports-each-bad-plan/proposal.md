# Proposal

## Why

The plan reader raises a raw pydantic `ValidationError` for a plan whose task group breaks a rule of `StageGroup`, so `devops roadmap plan-check` ends in a traceback and reports no problem (#3482). A run over the change folders of the tree reads 24 and raises `ValidationError` for 24. The spec of `roadmap-plan-check` says that the command reports the file and goes on. The round of the implement job will use the same reader, and it expects only `PlanReadError`.

Two more faults come with it. `validate_change` counts the INFO note of OpenSpec for `skip_specs` as a problem, so the stage job refuses each valid plan that sets `skip_specs`. The reader judges only the first verification command of the first task, but the implement step runs every command of every task.

## What Changes

- `read_change` in `src/devops_cli/roadmap/plan_read.py` turns the pydantic error of a task group into a `PlanReadError` for `tasks.md` that names the group, with the problems on one line.
- `read_change` judges every code span of every `Verification:` line of a group with `verification_problem`, and raises `PlanReadError` for each span that the step cannot run.
- `validate_change` in `src/devops_cli/roadmap/stage_validate.py` drops the one INFO message that OpenSpec gives for `skip_specs`, and keeps every other issue as a problem.
- The stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` tells the planner to write a sample file that no group creates as a bare name.
- The change carries a spec delta, because the plan-check output and the stage validation are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: The plan reader raises only a read error, The reader judges every verification command, Plan-check reports a plan that the model refuses
- `roadmap-stage`: The validation judges the change against the base specs, The stage prompt names a sample file by a bare name

## Impact

- Code: `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/stage_validate.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_plan_read.py`, `tests/roadmap/test_roadmap_plan_check.py`, `tests/commands/test_roadmap_plan_check_cmd.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- A run of `read_change` over the change folders of the tree at `origin/main` (59 folders, 2026-11-04) gave 24 reads, 24 `ValidationError` and 10 `PlanReadError`. The `ValidationError` came from `_group` in `src/devops_cli/roadmap/plan_read.py`, which runs outside the `try` of `read_change`.
- `uv run devops roadmap plan-check 3322` and `uv run devops roadmap plan-check 3329` ended in a pydantic error before the fix. After the fix, each prints one `read` problem and exits 1. `plan-check 3350` still prints its `body-length` and `stage` problems, and `plan-check 3339` still prints its `stage` problem.
- `openspec validate 1327-infra-commands-edge-fakes --strict --json` with OpenSpec 1.14.3 gives exit code 0 and one INFO issue: `skip_specs is set in .openspec.yaml: change declares no spec-level behavior changes, zero deltas accepted`. `validate_change` counted it as a problem.
- `src/devops_cli/roadmap/step_files.py` reads every code span of every `Verification:` line into `GroupTask.verification`, so the step runs all of them. `verification_problem` in `src/devops_cli/roadmap/implement_shell_policy.py` is the function that the step and the stage gate share.
- First check: `uv run devops ci fail-to-pass --base origin/main` on the new tests.

## Existing Tool Considered

pydantic already raises the `ValidationError` and gives `errors()` with a location and a message, and the reader uses that list. `verification_problem` is the shared judge of the step and the gate, and the reader calls it. The change builds no new helper for a parse, a path or a command, and adds no dependency. It deletes no internal code.

## Dependencies

None.
