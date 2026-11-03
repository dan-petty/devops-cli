# Proposal

## Why

A plan in the pull request for #3200 copied the bound of 40 characters from the issue text, while `SUMMARY_MAX_CHARS` is 60 and the plan stage prompt says 47. The spec scenario, the design decision and the code disagreed, and the plan check accepted the plan. #3308 makes a number beside a constant name a claim that the check compares with the staged tree.

## What Changes

- Add `src/devops_cli/roadmap/stage_constants.py`: it reads module-level integer constants of the staged Python files with `ast` and finds each constant name with a nearby number in a plan text.
- Call the new check from `check_proposal` in `src/devops_cli/roadmap/stage_change.py` over the texts that render to `proposal.md`, `design.md` and the spec deltas, and never over a group of `tasks.md`.
- Add the message that names the constant, the plan's number and the staged value to `src/devops_cli/lang/en/messages.py`.
- Add the rule that asks the model to cite the staged value of each constant that the plan relies on to `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- Add the requirements of the plan check of constant values to the capability `roadmap-stage`, with the tests of the new module.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan number beside a constant matches the staged value, A constant that the staged tree does not define is ignored, The check reads constants without running staged code, The task commands carry no constant claim, The prompt asks for the staged value of a constant

## Impact

- Code: `src/devops_cli/roadmap/stage_constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_change.py`, `openspec/changes/3308-plan-check-constant-value/.openspec.yaml`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `openspec/changes/3308-plan-check-constant-value/proposal.md`, `openspec/changes/3308-plan-check-constant-value/design.md`, `openspec/changes/3308-plan-check-constant-value/tasks.md`, `openspec/changes/3308-plan-check-constant-value/specs/roadmap-stage/spec.md`
- Tests: `tests/roadmap/test_roadmap_stage_constants.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- `read_file` on `src/devops_cli/roadmap/pull_form.py` showed `SUMMARY_MAX_CHARS: Final[int] = 60`, so the premise holds: the plan of the pull request for #3200 claimed 40.
- The probes give `The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.`, and that file holds `def check_proposal(` with `problems.extend(path_problems(proposal.groups, tree))`, so the plan check has one place for the new rule.
- The probes give `The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.`, so the prompt rule goes into a file of the commit.
- The probes give `The path `src/devops_cli/roadmap/stage_probe.py` is a file of the staging commit.`, and that file holds `probe_premise(source: Path, sha: str, body: str)`, the read-only probe that the new check follows.
- `search_code` for `PLAN_SUMMARY_MAX_CHARS` found it only in the plan folder `openspec/changes/3200-refuse-a-plan-with-placeholder-or/`, not in `src/`, so the check adds no constant of its own.
- First checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py`, then `uv run devops openspec check`, then `uv run devops roadmap eval stage --dry-run` to see the new gate on the golden set.

## Existing Tool Considered

Python's `ast` standard library covers the need, and the change adds no dependency. No open, maintained library compares a number in a plan with a named Python constant. The change builds its own code: 15,000 tokens to build, 4,000 tokens per month to keep and fix, and 1 to 2 elapsed days. It deletes no internal code.
