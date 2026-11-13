# Proposal: #4725

## Why

The stage job pushes plans that the CI job `Plan Check` then refuses. On 2026-11-13 the stage job logged `item=#5136 result=staged success=true gate_returns=0` (release 0.127.0) and opened plan pull request #5407. The `Plan Check` of #5407 failed: "Group 2, `Extend the naming-form and setup-step tests with the copilot names`, packs no file". The group changes `tests/invariants/test_workflow_contracts.py`, and only the command span of its verify line names that path, so the step of the group starts with no file to edit.

The stage gate and the CI check use different rules. `devops roadmap plan-check` measures each group and reports `group-no-files`, `group-over-budget`, a plan that the reader cannot read back, and the title and body rules. The stage job measures each group only against the budget. So each refusal costs one more push, one more CI run and a fix-plan round.

Closes #4725.

## What Changes

- `plan_check.py` gets `PlanFolder`, a change folder in memory with the checkout that the measure reads, and three functions: `form_problems` (the title and body rules), `folder_problems` (the plan reader, the stage gates and the size of each group) and `staged_problems` (both, for a plan that has no pull request yet). `plan_check` calls the same functions, so no rule has a second copy.
- The stage job runs `staged_problems` in `_Planner._settle` on the files that it writes, after `openspec validate` and before the change is ready. A reply that the rules refuse goes back to the model as a gate return of the gate `plan-check`, with the line that `devops roadmap plan-check` prints for each problem. A reply that the rules still refuse after the last return fails the item with the class `plan_defect`: the job pushes no branch and opens no pull request. The step `fix-plan` uses `_settle` too, so its revisions get the same check.
- The rules that need the pull request stay in the command only: the check `Semantic PR title`, a base spec that moved after the plan commit, and an open issue that the plan depends on. An open dependency holds the merge until the issue closes. It is no fault that the planner can fix, so the stage job does not return it.
- `plan_check` reads the change folder from the detached worktree of the head that it already makes for the measure, and no longer with `git show`. The plan reader and `openspec validate` then read the files that the stage job wrote, with their last line end. The gates get the registry of the head worktree, not of the working folder.
- `PlanProblem.line` gives the line of a problem. The command prints it, and the stage job returns it to the model.
- Tests: the head of #5407 is a fixture in `tests/fixtures/roadmap/plan_heads/5407-ecc08320bf60/`, and the check before the push gives its one CI problem word for word. Four stage tests had plans with a group that names no file that it changes, so CI would refuse them; their tasks now name the file. The planners of three test files planned on the repository root with a tree that lists `src/devops_cli/sample.py`, which the root does not hold; they now plan on a clone that holds the files of their tree.
- The change has a spec delta: the stage job refuses more replies.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-check`: The stage job and the command share the rules of a plan
- `roadmap-stage/replies`: The rules of the plan check refuse a reply before the push

## Impact

- Code: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/commands/roadmap.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan_check.py` (new), `tests/fixtures/roadmap/plan_heads/5407-ecc08320bf60/` (new), `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/stage/test_roadmap_stage_trace_runs.py`, `tests/roadmap/stage/test_roadmap_stage_plan_record_facts.py`
- Documents: `docs/roadmap/stage.md`, `docs/roadmap/plan-check.md`
- Release: the stage job and the step `fix-plan` run the code of the Service image and of the runner image, so the change acts only after a release. The `feat` commit makes release-please propose a minor release. No setting, no manifest and no metric changes. The refusals show in the existing log line `stage gate returns: ... gates=plan-check:<n> codes=plan-check:<n>`.

## Feasibility

- The premise is confirmed in the source at `origin/main` (2daf63a6c, release 0.128.0). `_Planner._settle` in `src/devops_cli/roadmap/stage/stage.py` measures the groups with `_fit` and stops only for a group over the budget (`OverBudget`). No code of `src/devops_cli/roadmap/stage/` reports a group that packs no file. `_size_problems` in `src/devops_cli/roadmap/plan_check.py` reports `group-no-files` for `item.files == 0` when the group changes a path that it does not create.
- `uv run devops roadmap plan-check 5407 --json` gives one problem: `group-no-files` for group 2 of `openspec/changes/5136-copilot-setup-hooks-refuse-commits-on/tasks.md`. The CI job log of #5407 (job 131882755175) gives the same line.
- History of the last 14 days: a GraphQL search found 154 plan pull requests of the Service opened from 2026-10-30 to 2026-11-13. The job `Plan Check` exists since 2026-11-07. Since then, the first commit (the push of the stage job) of 36 plan pull requests has a `Plan Check` result, and 7 of them failed (19 %). The job logs give the rules: `group-no-files` on #5407, #4104 and #3928 (#4104 also has `issue-dependency`), and `read` on #5032, #4963, #3960 and #3952. The 4 `read` failures are kind rules of the plan reader, which #5262 changed on 2026-11-12. No first commit of these pull requests failed a check other than `Plan Check`, so no invariant test failed on a stage push.
- The issue also asks for `devops ci test tests/invariants` before the push, after #4559. #4559 (a Job for each stage item) is open, and no stage push failed a test check in the 14 days. So this change adds no test run. The push gate of #4670 is the pre-push hook `branch-current`. The stage job already fetches the default branch and rebases onto it just before its push (`_rebase_onto_default`, #4380), so its push holds `origin/main`.
- #3970 and #3965 ask for the same refusal of `group-no-files` in `_settle`, with the logic of `plan_check._size_problems`. This change covers both: the stage job calls that rule, and a test proves that no branch reaches `origin`.
- Before the change, the two stage tests of `tests/roadmap/stage/test_roadmap_stage_plan_check.py` fail: the stage job stages the plan of the form of #5407 with one model call, and the apply step then reaches GitHub to open the pull request.

## Existing Tool Considered

`devops roadmap plan-check` holds the rules, and the change calls them from the stage job. No open tool checks the plans of this project. Cost: about 150,000 tokens and 3 hours to build, about 3,000 tokens a month to keep, about 15,000 tokens to fix. The change adds no rule; it moves the input of the rules from a pull request to a folder in memory.
