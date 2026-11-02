# Proposal

## Why

Draft readiness is decided in three places, each with its own rule, and the split let a partial implement pull request merge as #2801. #2916 asks for one function that decides for all four kinds (stage plan, implement, agent, person), called by the stage row, the implement job and devops pr ready, with devops pr check-readiness refusing a partial implement pull request and naming the unticked group.

## What Changes

- Add draft_readiness to src/devops_cli/roadmap/implement_pull.py: one input (pull request, kind, recorded item) and one answer (ready, wait, or refuse with a reason).
- Define complete per kind: stage plan when opened, implement when every task group is ticked and the change is archived, agent and person when their author says so, with optional extra checks as the seam for #2867.
- Make ready_to_mark of stage_ready.py call draft_readiness for the stage plan kind.
- Make the implement job call draft_readiness in implement_run.py before mark_ready.
- Make check_readiness in commands/pr.py and assess_merge_readiness in github/merge_readiness.py report the refusal as a blocker that names the unticked group.
- Add a table-driven test covering the four kinds with complete and incomplete cases.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge-readiness`: One readiness function decides for every kind of draft pull request, check-readiness names the unticked group

## Impact

- Code: `src/devops_cli/roadmap/implement_pull.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/github/merge_readiness.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_readiness.py`, `tests/roadmap/test_roadmap_stage_ready.py`, `tests/roadmap/test_roadmap_implement_job.py`, `tests/commands/test_pr.py`

## Feasibility

- list_files src/devops_cli/roadmap showed implement_pull.py and stage_ready.py, the modules that hold mark_ready and ready_to_mark.
- read_file src/devops_cli/roadmap/implement_pull.py showed mark_ready at line 127, the function that sends gh pr ready. The new decision function sits beside it.
- read_file src/devops_cli/roadmap/stage_ready.py showed ready_to_mark at line 64 and its docstring, 'This is the one seam of the decision (#2867)'. The stage row already routes its decision through one function.
- search_code mark_ready showed the only call sites: src/devops_cli/roadmap/implement_run.py:683 and src/devops_cli/roadmap/stage_ready.py:114.
- search_code check_readiness showed the command already exists at src/devops_cli/commands/pr.py:1472 and its plan at src/devops_cli/github/pr_plans.py:332, so this change extends that command instead of adding one.
- read_file src/devops_cli/github/merge_readiness.py showed assess_merge_readiness and its BlockerKind, where the refusal joins as one blocker.
- The premise holds: one function owns the decision for all four kinds, and no part of the item needs code that compensates for a missing tool.
- First checks against the real system: uv run devops pr check-readiness <pr> on the partial implement pull request (expects exit 1 and the unticked group named), and uv run devops ci for the full suite.

## Existing Tool Considered

gh pr ready, mark_ready in src/devops_cli/roadmap/implement_pull.py, ready_to_mark in src/devops_cli/roadmap/stage_ready.py, assess_merge_readiness in src/devops_cli/github/merge_readiness.py and read_check_runs in src/devops_cli/github/check_verdict.py cover the call, the reads and the command. The change builds only the glue: draft_readiness is about 120 tokens to write and about 40 tokens per fix cycle, one development session. It deletes no internal code: ready_to_mark keeps its name and becomes a call of draft_readiness.
