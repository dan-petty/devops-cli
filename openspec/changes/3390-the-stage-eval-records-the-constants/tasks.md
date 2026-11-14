# Tasks

## 1. Add the golden-set case of a wrong constant

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/case.json`, `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/facts.json`, `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/issue.txt`, `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_screen_eval.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/case.json` (new), `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/facts.json` (new), `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 1.1 The case `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/`, which the test `test_the_replay_catches_the_case_of_a_wrong_constant` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` replays; the test fails before the case exists
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 1.2 Copy the four files of `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/` into the new folder `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/`. In `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/plan.json`, replace `why` with the one-line sentence `The plan states that SUMMARY_MAX_CHARS is 40, so the summary limit is the staged bound.` and keep every other field. In `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/facts.json`, add `"constants": [["SUMMARY_MAX_CHARS", 60]]`, the value that `staged_constants` gives at base commit `89682e41118206c680e8d2273903d00d61ae140b`. In `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/case.json`, write issue 3410, pull 3435, the change `3410-the-stage-gate-proves-a-negative`, the merge and base commits of the good case, its title, the verdict `needs-fix`, the state `synthetic`, the scores of 4, a summary that says the plan states a wrong constant, and one defect of type `other`, severity `major`, gate `paths`, with the message `SUMMARY_MAX_CHARS is 60 in the staged tree, but the plan says 40.`. Add the name `3410-a-plan-that-states-a-wrong-constant` to half A of `tests/fixtures/roadmap_eval/stage/split.json`, which gives 30 names in each half. Add `test_the_replay_catches_the_case_of_a_wrong_constant` to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`: it loads the set, picks the case by its name, calls `replay_case`, asserts that its one outcome is `DefectStatus.CAUGHT` and that the message is in `replay.problems[GateName.PATHS]`, and asserts that `replay.failures` is empty
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 2. Hold the new case in the golden-set count test

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `tests/fixtures/roadmap_eval/stage/3410-a-plan-that-states-a-wrong-constant/facts.json`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`.

- [ ] 2.1 In `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, change the assertion of `test_the_set_holds_the_reviewed_plans_and_six_good_ones` from 59 cases to 60 and keep `EVALUATED_PULLS` at 53 pulls, because the new case reuses pull 3435. Add `test_a_case_reads_its_recorded_constants_and_an_old_case_holds_none` to that file: it picks the new case and a case whose facts record no constant, and asserts that the first holds `(("SUMMARY_MAX_CHARS", 60),)` and the second holds `()`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes

## 3. Move the pinned replay totals of the command

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_eval_command.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

- [ ] 3.1 In `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, move the totals of `test_the_replay_exits_0_and_lists_what_each_gate_caught` from `59 case(s), 6 good` to `60 case(s), 6 good` and from `82 of 319` to `83 of 320`, and move `test_the_replay_as_json_holds_the_totals_of_each_gate` to `{"judged": 83, "known": 320}`. The new case records one defect of type `other` at the gate `paths`, which the replay catches, so every gate keeps 0 missed
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_command.py` passes

## 4. Record the constants of a case with --record

Kind: behavior. Reads: `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_constants.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `docs/commands/roadmap.md`, `tests/roadmap/implement/test_roadmap_implement_amend.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_record.py` (new), `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/lang/en/messages.py`, `docs/commands/roadmap.md`, `tests/roadmap/stage/test_roadmap_stage_eval_record.py` (new).

- [ ] 4.1 `test_record_constants_writes_the_values_of_the_base_commit` in `tests/roadmap/stage/test_roadmap_stage_eval_record.py`: it copies a case folder to a temporary folder, gives `record_constants` a `staged_constants` that returns `{"SUMMARY_MAX_CHARS": 60}` and asserts that the facts file holds that pair and keeps its other keys; a second test asserts that the command with `--record` writes the file and names the case, and the test fails before the option and the module exist; the existing `tests/roadmap/implement/test_roadmap_implement_amend.py` keeps passing for the new message
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_record.py` fails on the base
- [ ] 4.2 Add `src/devops_cli/roadmap/stage/stage_eval_record.py` with `record_constants(case, source)` and `write_constants(folder, constants)`: `record_constants` validates `case.plan` as `StageProposal`, takes `candidate_names(plan_texts(proposal))`, calls `staged_constants(source, case.base_commit, names)`, and returns the name and value pairs sorted by name; `write_constants` rewrites only the `constants` key of `facts.json` and keeps every other key and the order of the file. Add a `record` option to `eval_stage_cmd` in `src/devops_cli/commands/roadmap_eval_stage.py` with a literal help text, as `src/devops_cli/commands/ai_gateway.py` does: it runs before the dry-run plan, selects the cases with `select_cases`, writes each case's facts file, prints one line for each case, exits 1 for a case whose base commit is `NO_COMMIT`, makes no model call and sends no request, and is refused together with `--dry-run`. Add the printed message to `src/devops_cli/lang/en/messages.py`, which `tests/roadmap/implement/test_roadmap_implement_amend.py` imports, so that test keeps passing. Add the unit test and the command test to `tests/roadmap/stage/test_roadmap_stage_eval_record.py`; both double the git read with the module's `staged_constants`, so they need no checkout, no client and no network
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_record.py` passes
- [ ] 4.3 Regenerate `docs/commands/roadmap.md` so the new `--record` option appears in its option table, and run `uv run devops docs generate`
  - Verification: `$ uv run devops ci docs` passes

## 5. Document the constants field of a case

Kind: other. Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`.

- [ ] 5.1 In `src/devops_cli/roadmap/stage/stage_eval_cases.py`, add `constants` to the `facts.json` bullet of the module docstring and to the `CaseFacts` docstring: the name and integer value pairs of the constants that the plan cites, with an empty tuple when the entry is absent or empty
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes
- [ ] 5.2 Edit the module docstring and the `CaseFacts` docstring in `src/devops_cli/roadmap/stage/stage_eval_cases.py` to name the `constants` field and its empty default
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
