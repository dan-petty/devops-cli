# Proposal

## Why

The stage job marks a plan pull request ready when the form gates and CI pass, so a plan whose own model review found a real defect still goes to review as if clean (#3264). The Service's round budget also counts such a plan as staged.

## What Changes

- The stage keeps a plan pull request in draft when the verification pass returns an open finding, applies the label `plan/needs-fix`, and puts the findings at the top of the stage comment.
- The row `stage_ready` refuses to mark a plan pull request ready while `plan/needs-fix` is present, and comments the reason.
- A plan with an open finding counts as a failed attempt of class `plan_defect` and not as a staged plan in the round budget.
- The golden set gains a case recorded from #3174, replayed by the existing `devops roadmap eval stage` command.
- The documentation of the stage job and the roadmap workflow states the open-finding stop.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: An open finding keeps the plan in draft, A plan with an open finding is a failed attempt, The Service marks a green stage pull request ready
- `roadmap-stage-eval`: The golden set holds a case of the open-finding stop

## Impact

- Code: `src/devops_cli/roadmap/stage_verify.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_ready.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/github/client.py`
- Documents: `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_stage_verify.py`, `tests/roadmap/test_roadmap_stage_verification.py`, `tests/roadmap/test_roadmap_run.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/case.json`, `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/issue.txt`, `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/plan.json`, `tests/fixtures/roadmap_eval/stage/3174-placeholder-plan/facts.json`, `tests/roadmap/test_roadmap_stage_eval_run.py`

## Feasibility

- The premise holds: the docstring of `src/devops_cli/roadmap/stage.py` says "A finding of the type `missing_path`, `false_premise` or `ignores_existing_code` that quotes its evidence sends the plan back to the planner once; every other finding goes into the comment of the item. The review never merges and never marks a draft ready."
- `docs/roadmap/stage.md` line 41 confirms it: "Every other finding goes into the comment, and the draft still opens."
- The probe `stage_ready` is defined at tests/roadmap/test_roadmap_run.py:882: `stage_ready=recent,` so the row already exists and a refusal there changes existing code.
- `read_file` on `src/devops_cli/roadmap/stage_verify.py` shows `Finding` with `type: DefectType` and the quote check of `returning`; the stage already holds the data that the open-finding stop needs, so no new model call is added. `PullStatus` in `src/devops_cli/github/client.py` adds `labels` so `stage_ready` inspects PR labels.
- `src/devops_cli/roadmap/failure.py` is the caller of `plan_defect` and `tests/roadmap/test_roadmap_failure.py` tests it, so the budget change reuses that class.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py`, `uv run devops ci test tests/roadmap/test_roadmap_stage_verification.py`, `uv run devops ci test tests/roadmap/test_roadmap_run.py`, `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool or library covers this need: the change modifies this repository's own roadmap stage job and `stage_ready` row. It reuses `stage_verify.Finding`, `stage_verify.returning` and `roadmap.failure` instead of new code, which keeps the cost at about 6,000 tokens to build, keep and fix, and about half a day elapsed.
