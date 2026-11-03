# Tasks

## 1. Read the staged integer constants and pair them with a plan number

Reads: `src/devops_cli/roadmap/stage_probe.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_constants.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_constants.py` (new).

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_constants.py`, assert that a source with `SUMMARY_MAX_CHARS: Final[int] = 60` gives 60, that an alias resolves to the integer in another module, that a value from a call is left out, that a name that two modules define with different values is left out, and that a plan text with `SUMMARY_MAX_CHARS` and 40 in one sentence yields one problem that names the constant, 40 and 60. Assert that a matching number yields no problem, that a note reference (`#2714`) and a line location (`:12`) are no candidate number, and that a sentence with two candidate numbers yields no problem. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/stage_constants.py` with `candidate_names(texts)`, `staged_constants(source, sha, names)` and `constant_problems(texts, constants)`. `staged_constants` finds each name with `git grep` under `src/` at `sha`, reads only the files it names with `git show`, parses them with `ast.parse`, resolves an alias across modules, and returns no value for an assignment that is no integer literal and no value for an ambiguous name. `constant_problems` splits a text into sentences, finds one known constant and one candidate number in a sentence, and returns one message for each number that differs, naming the constant, the plan's number and the staged value. Add the message to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py` passes

## 2. Refuse the plan in `check_proposal`

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_constants.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that `check_proposal` with `constants={"SUMMARY_MAX_CHARS": 60}` returns one problem for a proposal whose spec scenario says 40, returns none for one that says 60, returns none for a proposal with no constants, and returns none for the text of a task group that holds 40, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Add `plan_texts(proposal)` to `src/devops_cli/roadmap/stage_change.py`: the fields that render to `proposal.md`, `design.md` and each spec delta, with no task group. Add the `constants` keyword to `check_proposal` and add its problems to the list that the function returns. In `Stage._settle` in `src/devops_cli/roadmap/stage.py`, read the constants with `staged_constants(self._source, self._sha, candidate_names(plan_texts(proposal)))` and pass them to `check_proposal`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Ask the plan stage prompt for the staged value of a constant

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 Add one rule to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: cite the staged value of each constant that the plan relies on, with the constant name and its value, as `feasibility` quotes the probe lines, and give no new name to the bound of a constant that the staged tree defines. Add the assertion of that rule to `tests/roadmap/test_roadmap_stage_prompt_rules.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes

## 4. Carry recorded constants through the stage eval replay

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 4.1 In `tests/roadmap/test_roadmap_stage_eval_gates.py`, assert that a case with no `constants` field replays as it does today, and that a case with `constants` refuses a plan whose spec scenario names a different value. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 4.2 Add `constants: tuple[tuple[str, int], ...] = ()` to `CaseFacts`, and a `constants` field with an empty default to `PlanUnderTest`. `PlanUnderTest.of_case` reads `dict(case.facts.constants)`, and `_path_gate` passes `plan.constants` to `check_proposal`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 5. Check the OpenSpec change against the base specs

Reads: `openspec/config.yaml`. Changes: `openspec/changes/3308-the-plan-check-compares-a-number/proposal.md`, `openspec/changes/3308-the-plan-check-compares-a-number/design.md`, `openspec/changes/3308-the-plan-check-compares-a-number/tasks.md`, `openspec/changes/3308-the-plan-check-compares-a-number/.openspec.yaml`, `openspec/changes/3308-the-plan-check-compares-a-number/specs/roadmap-stage/spec.md`.

- [ ] 5.1 Keep the change folder `openspec/changes/3308-the-plan-check-compares-a-number/` with its proposal, its design, its `tasks.md` and the spec delta of `roadmap-stage`, then run the validation
  - Verification: `uv run devops openspec check` passes
- [ ] 5.2 The change folder is the record of the item, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Criteria

- Group 2: The plan check SHALL refuse a plan when one known integer constant and one candidate number in a sentence differ from the staged value.
- Group 2: The plan check SHALL accept a plan when the number beside a known integer constant equals the staged value of that constant.
- Group 1: The plan check MUST ignore a constant name that the staged tree does not define as a module-level integer constant.
- Group 1: The plan check MUST skip a sentence with more than one candidate number and a name that two modules define with different values.
- Group 2: The plan check MUST NOT compare a number in `tasks.md` with a constant.
- Group 4: The stage eval replay MUST read recorded constants and MUST read no git.
- Group 3: The plan stage prompt SHALL tell the model to cite the staged value of each constant that the plan relies on.
- Group 1: The plan check MUST read constant values with Python AST and MUST NOT import or execute staged code.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
