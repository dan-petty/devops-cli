# Proposal

## Why

A plan can put a number beside a constant name that is not the value in the staged tree. The plan of the pull request for #3200 gave a summary bound of 40 in a spec scenario, while `SUMMARY_MAX_CHARS` is 60 in `src/devops_cli/roadmap/pull_form.py` and `STAGE_SUMMARY_MAX_CHARS` is 47. The plan check accepted it. #3308 makes that number a claim that the check compares with the staged tree, and the plan stage prompt asks the model to cite the staged value first.

A sentence that holds more than one number is ambiguous: it can show an example, a note or a second bound. The check skips it, so a valid plan is not refused. A constant name that the tree does not define is skipped too; the prompt rule asks the model to cite the existing constant instead of giving its bound a new name.

## What Changes

- Add `src/devops_cli/roadmap/stage/stage_constants.py`:
  - `candidate_names(texts)` reads the constant names that the plan text cites.
  - `staged_constants(source, sha, names)` finds the definition of each name with `git grep` at the staging commit, reads only those files with `git show`, parses them with `ast`, and resolves an alias across modules. It imports and runs no staged code.
  - `constant_problems(texts, constants)` returns one problem for each sentence that names one known constant and holds one candidate number that differs.
- Add `plan_texts(proposal)` to `src/devops_cli/roadmap/stage/stage_change.py`: the plan fields that render to `proposal.md`, `design.md` and the spec deltas. It leaves out every task group, so `tasks.md` is never scanned.
- Add a `constants` keyword to `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py`, and pass the mapping that `Stage._settle` reads with `staged_constants` from `self._source` and `self._sha`.
- Carry recorded constants through the stage eval replay: `CaseFacts` gets an optional `constants` field, and `PlanUnderTest` passes it to `check_proposal`. A case with no field keeps an empty mapping, so the recorded cases do not change.
- Add the message that names the constant, the plan's number and the staged value to `src/devops_cli/lang/en/messages.py`.
- Add the citation rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: cite the staged value of each constant that the plan relies on, and do not give a new name to the bound of a constant that the staged tree defines.
- Add the requirements to `roadmap-stage`, with the tests of the new module.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan number beside a constant matches the staged value, A constant that the staged tree does not define is ignored, The check reads constants without running staged code, The task commands carry no constant claim, The replay passes recorded constants, The prompt asks for the staged value of a constant

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_constants.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_constants.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`

## Feasibility

- `read_file` on `src/devops_cli/roadmap/pull_form.py` showed `SUMMARY_MAX_CHARS: Final[int] = 60`, and `src/devops_cli/roadmap/stage_change.py` showed `STAGE_SUMMARY_MAX_CHARS: Final[int] = SUMMARY_MAX_CHARS - summary_length(`, so the premise holds: the plan of the pull request for #3200 claimed 40.
- The probes give `The path `src/devops_cli/roadmap/stage_change.py` is a file of the staging commit.`, and that file holds `def check_proposal(` with `problems.extend(path_problems(proposal.groups, tree))`, so the plan check has one place for the new rule.
- The probes give `The path `src/devops_cli/roadmap/stage_paths.py` is a file of the staging commit.`, and `class StagedTree` holds `self._files = frozenset(files)` and no text of a file. The content therefore comes from `Stage._settle`, which holds `self._source` and `self._sha` and calls `check_proposal(`, and not from the tree.
- The probes give `The path `src/devops_cli/roadmap/stage_probe.py` is a file of the staging commit.`, and that file holds `probe_premise(source: Path, sha: str, body: str)`, the read-only probe that the new reader follows with `git grep` and `git show`.
- `src/devops_cli/roadmap/stage/stage_change.py` holds `def render_change(` and `def _spec_file(`, so the plan fields that render to the change files are known and the check can read them without the change folder name.
- `src/devops_cli/roadmap/stage/stage_eval_cases.py` holds `class CaseFacts` with `tracked` and `capabilities`, so the replay holds no file text. An optional `constants` field keeps every recorded case valid and lets a later case record the values.
- The plan of the pull request for #3260 said `StageProposal.summary` takes the bound `PLAN_SUMMARY_MAX_CHARS = 47`, and that the issue text says 40 and the schema says 60. The staged tree defines no `PLAN_SUMMARY_MAX_CHARS`, so the check skips that name, as the design decided to avoid a false refusal. The check refuses the explicit claim that the issue records, `SUMMARY_MAX_CHARS` beside 40, and the prompt rule makes the model state the staged 60.
- The probes give `The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.`, so the prompt rule goes into a file of the commit.
- First checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_constants.py`, then `uv run devops openspec check`, then `uv run devops roadmap eval stage --dry-run` to see the gate on the golden set.

## Existing Tool Considered

Python's `ast` standard library covers the need, and the change adds no dependency. No open, maintained library compares a number in a plan with a named Python constant. The change builds its own code: 15,000 tokens to build, 4,000 tokens per month to keep and fix, and 1 to 2 elapsed days. It deletes no internal code.
