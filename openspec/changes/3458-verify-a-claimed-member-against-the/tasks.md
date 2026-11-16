# Tasks

## 1. Refuse a member that the staged class lacks

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/stage/test_roadmap_stage_class_claim.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_models.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_class_claim.py`.
Adds: `parse_class_members`, `stage_problem_class_member`

- [x] 1.1 `tests/roadmap/stage/test_roadmap_stage_class_claim.py` fails on the base: `test_a_member_claim_the_staged_class_lacks_is_refused` refuses a decision that names `TaskGroup.kind` and quotes `class TaskGroup:`, `test_a_member_claim_the_staged_class_defines_passes` accepts a decision that names `TaskGroup.tasks` and quotes `tasks: tuple[GroupTask, ...]`, and `test_the_member_rule_accepts_the_plan_of_this_change` builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_class_claim.py` fails on the base
- [x] 1.2 Add `parse_class_members` to `src/devops_cli/roadmap/stage/stage_models.py`: it parses the class source with the standard library `ast` and gives the fields, the methods and the nested classes of the class body. Extend `class_claim_problems` in `src/devops_cli/roadmap/stage/stage_change.py`: a code span of the form `Class.member` is refused when the member set of that class at the staged commit lacks the member. Add `stage_problem_class_member` to `src/devops_cli/lang/en/messages.py`, naming the class, the member and the plan section. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_class_claim.py` passes

## 2. Refuse a claim line that names a module with no statement

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_gates.py`.
Adds: `module_quote_problems`, `stage_problem_module_quote`

- [ ] 2.1 `tests/roadmap/stage/test_roadmap_stage_gates.py` fails on the base: `test_a_claim_line_that_names_a_module_with_no_statement_is_refused` refuses a `feasibility` line that names `src/devops_cli/roadmap/step_files.py` and holds no statement of it, `test_a_claim_line_that_quotes_its_module_passes` accepts the same line with `class TaskGroup:` in a second code span, and `test_the_module_quote_rule_accepts_the_plan_of_this_change` builds the plan's own `StageProposal` and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` fails on the base
- [ ] 2.2 Add `module_quote_problems` to `src/devops_cli/roadmap/stage/stage_change.py` and call it in the `citation` gate beside `_plan_citation_problems`: a code span of a design decision, a rejected alternative or a `feasibility` line that is a module path under `src/` needs another code span of the line whose whitespace-squashed text is at least three characters and occurs in the text of that module at the staged commit, and a module whose text the reader does not give is not judged. Add `stage_problem_module_quote` to `src/devops_cli/lang/en/messages.py`. Give the `feasibility` line of the trace-facts plan in `tests/roadmap/stage/test_roadmap_stage_gates.py` a statement of the module it names, and add the cases of the rule. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gates.py` passes

## 3. State the quote rule in the verification prompt and score it

Kind: behavior. Reads: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base: `test_the_review_refuses_a_line_that_names_a_source_with_no_statement` loads `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and asserts that the `false_premise` rule names a line that quotes no statement of its module
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 3.2 State in `src/devops_cli/ai/tasks/roadmap_stage_verify.md` that a line which names a type, a member or a module under `src/` and quotes no statement of its module is a `false_premise` finding, so the model review refuses such a line. Add `test_the_review_refuses_a_line_that_names_a_source_with_no_statement` to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Run `uv run devops roadmap eval verify --model <baseline-model> --source .` on the base commit and on the change with the same model, and state the score before and after the change in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 3.3 Edit `src/devops_cli/ai/tasks/roadmap_stage_verify.md` to state the `false_premise` rule for a line that names a source and quotes no statement of its module
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
