# Tasks

## 1. Refuse a class claim that the staged source lacks

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_models.py`, `tests/roadmap/stage/test_roadmap_stage_apply.py`. Changes: `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_class_claim.py` (new).

- [x] 1.1 Write `test_class_sources_reads_a_class_with_no_base` first: it calls `class_sources(REPO_ROOT, "HEAD", ["StagedTree"])` and asserts that the source holds `ls-files`, so it fails on the base because the reader does not exist. Then write `test_a_decision_that_names_a_class_with_no_quote_is_refused`, `test_a_decision_that_quotes_the_class_passes` with a decision that names `StagedTree.read` and quotes `ls-files`, `test_a_quote_the_class_lacks_is_refused` with `file text`, `test_a_name_that_no_class_under_src_defines_is_no_claim` with `ConfigDict`, `test_a_quote_of_two_characters_is_refused` with `ls`, and `test_the_problem_names_the_class_and_the_section` in `tests/roadmap/stage/test_roadmap_stage_class_claim.py`: each calls `check_proposal` with a plan and a mapping from class name to source, and asserts the `stage_problem_class_claim` problem or its absence. Add `test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_class_claim.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_models.py`, add `class_sources(source, sha, names)` beside `model_fields`: it greps `^class <name>` under `src/` at the staged commit, reads each module with `git show`, parses it with `ast`, and returns the source segment of each named class, so a class that declares no base is read. In `src/devops_cli/roadmap/stage/stage_change.py`, add `claimed_classes(proposal)` and `class_claim_problems(proposal, classes)`: a code span that starts with a class name is a claim, and the line needs another code span of at least three characters whose whitespace-squashed text occurs in the squashed class source. Call the second in `ProposalGate.PATHS` beside `model_problems`, and give `check_gates` and `check_proposal` an optional `classes` mapping that defaults to None. In `src/devops_cli/roadmap/stage/stage.py`, compute the mapping with `class_sources` from the names that `claimed_classes` returns, beside the model fields, and pass it to `check_gates`. Add `stage_problem_class_claim` to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`. The writes of the stage job stay as they are, and `tests/roadmap/stage/test_roadmap_stage_apply.py` covers them with no change. Run `uv run devops roadmap eval stage --replay` on the base commit and after the change, and state the score before and after
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_class_claim.py` passes

## 2. Carry the class sources into the replay case facts

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 2.1 Write `test_the_paths_gate_refuses_a_false_class_claim` and `test_the_paths_gate_accepts_a_class_claim_that_quotes_the_class` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`: a plan whose decision names `StagedTree` with no quote of the class fails the `paths` gate, and the same decision with a span that holds `ls-files` passes it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 2.2 Add the field `classes: Mapping[str, str]` to `CaseFacts` in `src/devops_cli/roadmap/stage/stage_eval_cases.py`, empty by default. Add `classes` to `PlanUnderTest` in `src/devops_cli/roadmap/stage/stage_eval_gates.py`, fill it from the facts in `of_case`, and pass it to `check_proposal` in `_path_gate`. Run `uv run devops roadmap eval stage --replay` on the base commit and after the change, and state the score before and after
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 3. Add the golden case of the false class claim

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/3344-a-plan-that-reads-an-absent-field/case.json`, `tests/fixtures/roadmap_eval/stage/3344-a-plan-that-reads-an-absent-field/facts.json`, `tests/fixtures/roadmap_eval/stage/3344-a-plan-that-reads-an-absent-field/plan.json`, `tests/fixtures/roadmap_eval/stage/split.json`, `tests/gate/roadmap_stage_eval_commits.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/case.json` (new), `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/facts.json` (new), `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/plan.json` (new), `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`.

- [ ] 3.1 Write `test_the_case_of_a_false_class_claim_is_recorded` in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`: it loads the case, asserts that its one defect has the type `false_premise` and the gate `paths`, asserts that the facts hold the source of `StagedTree`, and asserts that a note says the case reads no commit
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` fails on the base
- [ ] 3.2 Write the four files of `tests/fixtures/roadmap_eval/stage/3407-a-plan-that-claims-a-class-holds/`: `case.json` with the issue and the pull 3407, the two null commits, a note that says the case reads no commit, one defect of the type `false_premise` at the gate `paths` with a message that the problem holds, and the summary of the false claim; `facts.json` with the tracked files that the plan names, the capability `roadmap-stage/claims`, and the source of `StagedTree` under `classes`; `issue.txt` with the body of #3407; and `plan.json` whose design decision claims that `StagedTree` holds the file text and quotes no text of the class, and whose other gates find no problem. Add 3407 to `EVALUATED_PULLS`, raise the two literals of `test_the_set_holds_the_reviewed_plans_and_six_good_ones` to 60 cases and 54 pulls, and add the case name to half A of `tests/fixtures/roadmap_eval/stage/split.json`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes

## 4. Raise the judged baseline for the new case

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 4.1 Raise `JUDGED_BASELINE` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` from `(82, 319)` to `(83, 320)`, and add a comment line that names the case of #3407 as the one caught defect and the one defect. The function that the raised constant answers is `test_the_counts_of_each_type_are_the_baseline_that_a_change_of_a_gate_beats`, which asserts `report.judged() == JUDGED_BASELINE`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## 5. State the class-claim rule of the paths gate

Kind: other. Reads: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage/stage_change.py`. Changes: `docs/roadmap/plan-recheck.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 State the class-claim rule in the `paths` row of the gate table of `docs/roadmap/plan-recheck.md` and in the list of the rules of the `paths` gate of `docs/ROADMAP_WORKFLOW.md`: a decision, a rejected alternative or a feasibility line that names an internal class in a code span gives another code span that holds text of that class at the staged commit, and a class that declares no base is read too
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/roadmap/plan-recheck.md` and `docs/ROADMAP_WORKFLOW.md` with the class-claim rule of the `paths` gate
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
