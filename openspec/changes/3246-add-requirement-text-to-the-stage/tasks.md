# Tasks

## 1. Select the requirement text in stage_specs

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_specs.py`, `src/devops_cli/roadmap/step_files.py`, `tests/roadmap/stage/test_roadmap_stage_specs.py`. Changes: `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_specs.py`.

- [ ] 1.1 `test_a_cited_command_brings_the_requirement_text`, `test_the_count_bound_cuts_the_requirement_text`, `test_the_character_bound_cuts_the_requirement_text`, `test_a_name_match_comes_before_a_text_match` and `test_read_spec_answers_a_capability_outside_the_bound` in `tests/roadmap/stage/test_roadmap_stage_specs.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py` fails on the base
- [ ] 1.2 Add `REQUIREMENT_TEXT_MAX_COUNT` (12) and `REQUIREMENT_TEXT_MAX_CHARS` (6000) to `src/devops_cli/roadmap/stage/stage_specs.py`, each with a one-line docstring string beneath it, and add `requirement_text(specs, *, title, body)`. It takes the code spans of the title and the body with `code_spans` of `src/devops_cli/roadmap/step_files.py`, marks a requirement as a name match when the text cites its capability or its name, and as a text match when its statement holds one of those code spans, folded and in one case. It writes the name matches in file order, then the text matches in file order, keeps at most the count constant's number of requirements and drops each one that would pass the character constant, writes one line for each kept requirement as a dash, the capability, the name and the statement, and returns an empty string when nothing matches
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_specs.py` passes

## 2. Add the requirement text to the plan request context

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [ ] 2.1 `test_the_request_context_holds_the_text_of_a_cited_requirement` in `tests/roadmap/stage/test_roadmap_stage_plan.py`, on a fake spec whose one requirement names a command that the item cites: it asserts that the context holds the `### Requirement text` section with that name and its text, and that no section appears when nothing matches
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 In `_Planner._request` of `src/devops_cli/roadmap/stage/stage.py`, append a `### Requirement text` section to the context after the `### Registry places` section, built by `requirement_text(self._specs, title=item.title, body=item.body)`, and append nothing when the selection is empty. The section stays empty when the checkout holds no base spec that matches the item, so the first-request count of `tests/roadmap/stage/test_roadmap_stage_window.py` stays as it is
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 3. Give the review the same requirement text

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`.

- [ ] 3.1 `test_the_review_input_carries_the_requirement_text` in `tests/roadmap/stage/test_roadmap_stage_verify.py` and `test_a_conflicting_added_requirement_that_quotes_the_context_stays_open` in `tests/roadmap/stage/test_roadmap_stage_verification.py`; the first asserts the payload key and the quote, the second runs a plan against a fake spec whose requirement states the behavior and asserts that the finding stays open
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_verification.py` fails on the base
- [ ] 3.2 Add `requirements: str = ""` to `VerificationInput` of `src/devops_cli/roadmap/stage/stage_verify.py`, write it in `payload` when it is not empty, carry it in the base input of `of` so the window accounting holds, and yield it in `request_texts`. Give `of` a keyword `specs: Mapping[str, BaseSpec] | None` and fill the field with `requirement_text(specs, title=title, body=body)` when the caller passes the base specs. In `_Planner._input_of` of `src/devops_cli/roadmap/stage/stage.py`, pass `specs=self._specs`. Update `test_a_first_review_keeps_its_request_and_its_prompt` and `test_the_verifier_gets_the_issue_the_plan_and_the_cited_files_once_the_gates_pass` for the new key
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py tests/roadmap/stage/test_roadmap_stage_verification.py` passes

## 4. Add the golden-set case of the conflict of #3225

Kind: manifest. Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/plan_read.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`. Changes: `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/case.json` (new), `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/facts.json` (new), `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [ ] 4.1 The case `tests/fixtures/roadmap_eval/stage/3225-a-plan-adds-a-requirement-that/case.json` and `test_the_case_of_the_conflict_of_3225_holds_its_defect_and_its_stated_requirement` in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`: the test loads the set, and asserts that the case holds one `spec_delta_wrong` defect with the gate `none`, a `where` that names the added requirement of the delta, a `problem` that says the plan restates a base requirement, and an `evidence` that is the text of the base requirement of `roadmap-implement-step` that the added requirement states again
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` fails on the base
- [ ] 4.2 Create the four files of the case from the review of pull 3225, whose plan was of issue 3060. Read the merge commit with `git log --grep='(#3225)' --format=%H` and its parent, read the body of issue 3060 with `gh issue view 3060 --json title,body`, and write `plan.json` as the reply that `read_change` of `src/devops_cli/roadmap/plan_read.py` returns for the change folder of issue 3060 at that merge commit. Write `case.json` with every key that `StageCase` requires: `issue` 3060, `pull` 3225, `title` the title of pull 3225, `change` the change folder of issue 3060, `merge_commit` the merge commit, `base_commit` its parent, `verdict` `needs-fix`, `state` `merged`, `scores` the five scores of the review, `summary` one line of what the review found, and `notes` the line that the plan is the plan of issue 3060. Write its one defect with every key that `Defect` requires: `type` `spec_delta_wrong`, `severity` `major`, `where` the added requirement of the delta of `roadmap-implement-step`, `problem` the sentence that the plan adds a requirement that states a behavior that a base requirement already states instead of changing that requirement, `evidence` the quoted text of that base requirement, `gate` `none` because the name check passes a new name, and `reason` the sentence that the recorded plan passes the duplicate-name check so no gate of the job refuses it. Write `issue.txt` as the body of issue 3060 only, since `_read_case` reads it as `issue_body`, and write `facts.json` with the key `tracked` for the tracked files that the gates need and the key `capabilities` for `roadmap-implement-step`. When the recorded plan fails the schema of `StageProposal`, name the `kind` gate on the defect, as the set requires
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` passes

## 5. Register the case of #3225 in the golden set

Kind: other. Reads: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`.

- [ ] 5.1 Add 3225 to `EVALUATED_PULLS` in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, and raise the two literals of `test_the_set_holds_the_reviewed_plans_and_six_good_ones` to 60 cases and 54 pulls, so the set holds the new reviewed case
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py` passes

## 6. Replay the case of #3225 through the review

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_specs.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage/stage_verify_eval.py`, `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`.

- [ ] 6.1 `test_the_replay_of_the_case_of_3225_returns_the_plan_for_its_conflict` in `tests/roadmap/stage/test_roadmap_stage_verify_eval.py`: it writes a spec of one requirement whose statement is the evidence of the case of #3225 into the sample repository with `track`, scripts the OpenSpec fake to list that capability, copies the case of #3225 at that commit with an `issue_body` that cites the requirement name, answers the pass with one finding of the type `spec_delta_wrong` whose quote is that statement, and asserts that the request holds the quote in `requirements` and that the finding returns the plan
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` fails on the base
- [ ] 6.2 In `_run_cases` of `src/devops_cli/roadmap/stage/stage_verify_eval.py`, read the base specs of the checkout of the case with `read_base_specs(source, tool)` and pass them to `VerificationInput.of` as `specs`, so the replay of a case reads the same requirement text as the plan run of the item. Write the test first with a fake model that answers the one finding whose quote is the stated requirement of the case
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_eval.py` passes

## 7. Tell the planner and the review about the requirement text

Kind: other. Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `docs/roadmap/stage.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `docs/roadmap/stage.md`.

- [ ] 7.1 Add to the capability rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md` the instruction that the planner changes a requirement of the `### Requirement text` section of the context with modified when that requirement states the behavior. Add `requirements`, the bounded text of the base requirements that the item cites, to the key list of `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and say that a quote may come from it. Add `test_the_prompt_says_to_use_modified_for_a_stated_behavior` and `test_the_verify_prompt_names_the_requirement_text` to `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change with the same model, and state the score before and after the change in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 7.2 Edit `docs/roadmap/stage.md` so the Capabilities row of the first-request table names the requirement text, its two bounds and the read-spec tool for the rest
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: A test with a fake spec shows that a plan that cites a command named in a requirement gets that requirement in the context.
- Group 1: The bound is a named constant with a docstring, and a test shows the cut.
- Group 6: The model verification pass (`stage_verify.py`) receives the same text, and a replay case shows a conflict that it now finds (a case from #3225 or #3228).
- Group 7: The prompt tells the planner to use MODIFIED when a requirement of the context states the behavior.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
