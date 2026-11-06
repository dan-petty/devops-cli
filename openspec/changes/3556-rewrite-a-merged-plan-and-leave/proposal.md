# Proposal

## Why

#3556: `devops roadmap plan-recheck` (#3492) reports each merged plan with one result and writes nothing. On `origin/main`, 21 of 42 live folders have no `Verification:` line, 25 of 42 fail the plan reader, and the report shows `rewrite` for no folder. A person can not act on the report, because no command rewrites a plan. This change adds the mechanical rewrite. The report then names `rewrite` only for a plan that the rewrite fixes, and `--confirm` writes the result for a person to review.

## What Changes

- Add `rewrite_plan` in the new module `src/devops_cli/roadmap/plan_rewrite.py`. It works on parsed task groups. It adds a `Verification:` line to each group that has none, changes a sample path in a task to a bare name, and adds a `design.md` stub when the folder has none. It changes no other line.
- The command of a new `Verification:` line comes from the plan: `uv run devops ci test` with the test files of the `Changes:` line of the group, or `uv run devops ci docs` when the group changes only documents. A command that `read_verification` refuses is not written, and the group stays as it is.
- `recheck_plans` applies the rewrite in memory and judges the rewritten plan with `read_change`, `check_gates` and `openspec validate`. A plan gets `rewrite` only when the rewritten plan passes all three. A plan that the rewrite does not fix gets `new-plan`, and its refusals come from the rewritten plan.
- `plan-recheck --confirm` writes the rewritten files of the `rewrite` folders to the working tree of the checkout that `--source` names. It refuses a file that differs from the default branch, and it makes no commit. Without `--confirm` the command writes nothing.
- A merged plan with no way forward already leaves the implement queue with the left-out reason of #3393 (`implement_left_plan`), and `devops roadmap explain` names its first problem. A test now holds this for a Planned item, as the staged branch has one already.
- `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md` and the help text of the command say what the rewrite does, and the generated command documents follow.
- Delete the note `plan_recheck_no_verification`: a plan that passes and that the rewrite does not change is `ok`, and the count of folders with no `Verification:` line still shows it.
- The change fits one pull request.
- The change commits no rewritten live plan. The live plans of #3187, #2441 and #2610 belong to another item.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-plan-recheck`: A rewrite is judged in memory and `rewrite` means that the rewritten plan passes; the rewrite is mechanical and keeps the task groups; `--confirm` writes the rewrite; a plan with no way forward leaves the implement queue with the reason of #3393.

## Impact

- Code: `src/devops_cli/roadmap/plan_rewrite.py` (new), `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`, `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`
- Tests: `tests/roadmap/test_roadmap_plan_rewrite.py` (new), `tests/roadmap/test_roadmap_plan_recheck.py`, `tests/roadmap/test_roadmap_implement_plan_reason.py`, `tests/commands/test_roadmap_plan_recheck_cmd.py` (new)

## Feasibility

- The premise holds. Output of `uv run devops roadmap plan-recheck --source .` on `origin/main` at `ffaea530`: `21 of 42 folders have no Verification: line.`, `25 of 42 folders fail the plan reader.` and `Results: ok 2, rewrite 0, new-plan 40, delivered 0, cleanup 5.` So the report names `rewrite` for no folder today.
- The reader errors show what a rewrite can fix. `2116`, `2162`, `2462` and 9 more folders fail with "has the kind other, and it has neither verify nor process". `2469`, `2579` and `2644` fail with "has the kind behavior, and it has no verify". These groups lack the `Verification:` line, and their `Changes:` line names the test files that the command needs. `3427` and `3318` name `tests/test_sample.py` and `.agents/skills/openspec-x/SKILL.md` in a task: the paths gate refuses them, and the stage prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md` line 24 says that a sample file gets a bare name.
- The left-out reason exists. `src/devops_cli/roadmap/implement.py` holds `_plan_reason` (line 379), which returns `implement_left_plan` with the first problem of `check_proposal`, and `_planned_target` calls it for a Planned item (line 353). `tests/roadmap/test_roadmap_implement_plan_reason.py` covers the staged branch only, so this change adds the Planned case. #3393 and #3492 are merged, so both dependencies are met.
- A plan with no `Verification:` line is not always fixable. A group whose `Changes:` line names no test file and no document gets no command, because no text of the plan gives one. Such a plan stays `new-plan`, and the reader error is its reason. The rewrite does not guess a command.
- First checks of the work: `uv run devops ci test tests/roadmap/test_roadmap_plan_rewrite.py tests/roadmap/test_roadmap_plan_recheck.py` must pass, and `uv run devops roadmap plan-recheck --source . --branch HEAD` in the checkout must show no new refusal for the folder of this change.

## Existing Tool Considered

No outside tool rewrites an OpenSpec plan: the OpenSpec CLI validates and archives a change but does not edit `tasks.md`. The change builds the rewrite on `parse_task_groups` (a `markdown-it-py` parser, already a dependency) and on the project code `read_change`, `read_verification` and `check_gates`, and it adds no parser. Written cost to build: about 250k tokens and 2 days of elapsed time. Written cost to keep and fix: about 30k tokens each month. The change deletes the message `plan_recheck_no_verification` and the rule of `_record` that gave `rewrite` to a plan on its text before any rewrite.
