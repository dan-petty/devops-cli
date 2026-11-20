# Tasks

## 1. Name the failed criterion and part in the form-check failure

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`.
Adds: `form_check_details`

- [x] 1.1 `test_a_form_check_failure_names_the_criterion_and_part` in `tests/roadmap/refine/test_roadmap_refine_job_failure.py`: it builds a reply whose first criterion has an empty `then`, asserts that `form_check_details` gives `acceptance_criteria[0].then` and that `refine.failure` names it, and updates the expectation of `test_a_proposal_that_fails_a_form_check_makes_no_person_wait_and_counts_the_try`, which asserts that `refine.next_step` is `retry` and that the failure names the empty part
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_job_failure.py` fails on the base
- [x] 1.2 Add `form_check_details` to `src/devops_cli/roadmap/refine/refine.py`: it returns `problem_statement` and `existing_tool` for an empty field, and `acceptance_criteria[<index>].<part>` for each empty part of a criterion, read from the same `model_dump` that `_complete` reads. Add the message `refine_failure_form_parts` to `src/devops_cli/lang/en/messages.py`. Let `_job_failure` append that text with the details of `form_check_details`, so `refine.failure` names the criterion and the part, and remove the branch that returns the generic text alone. Leave `form_checks` as it is
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_job_failure.py` passes

## 2. Remove the two refine character caps

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`.

- [x] 2.1 `test_no_character_cap_cuts_a_refine_failure` in `tests/roadmap/refine/test_roadmap_refine_job_failure.py` reads `src/devops_cli/config/constants.py` and asserts that neither cap name is defined; `test_a_long_open_question_does_not_cut_the_searches_from_the_failure` drops its length assertion and asserts that the whole long question stays in `refine.failure` and that the text ends with the searched call
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_job_failure.py tests/roadmap/test_roadmap_limit_classes.py` fails on the base
- [x] 2.2 Delete `CONST_ROADMAP_REFINE_FAILURE_MAX_CHARS` and `CONST_ROADMAP_REFINE_JUDGE_FINDINGS_MAX_CHARS` from `src/devops_cli/config/constants.py`, with their imports in `src/devops_cli/roadmap/refine/refine.py`. Remove the cut in `_job_failure` with its comment, the slice of the first finding in `_refusal`, the cut of the findings in `_failure_marks`, and the sentence of the class docstring at `src/devops_cli/roadmap/refine/refine.py:427:class JobFailure:` that names the cap. Drop the two entries from `LIMITS` in `tests/roadmap/test_roadmap_limit_classes.py`, so its registry test still matches the code
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_job_failure.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 3. Give the whole earlier failure to the next request

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, `tests/roadmap/refine/test_roadmap_refine_job_failure.py`.

- [x] 3.1 `test_an_empty_then_reaches_the_record_and_the_next_request` in `tests/roadmap/refine/test_roadmap_refine_job_failure.py` runs a round whose first criterion has an empty `then`, asserts that `refine.failure` names `acceptance_criteria[0].then`, then runs the next round and asserts that its `judge_findings` hold that text; `test_the_next_request_carries_a_failure_longer_than_2000_characters` calls `_judge_findings` with a long recorded failure and asserts the whole text once
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_job_failure.py` fails on the base
- [x] 3.2 Let `_judge_findings` in `src/devops_cli/roadmap/refine/refine.py` return the recorded `refine.failure` beside the lines of `refine.judge_findings`, once, so the next request carries the whole earlier failure. Record each prompt in `_Client` in `tests/roadmap/refine/test_roadmap_refine_job_failure.py`, so the test reads the request. Name the failure of the earlier try beside the review findings in the first and the ninth paragraph of `src/devops_cli/ai/tasks/roadmap_refine_proposal.md`, so the model fixes it
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_job_failure.py` passes

## 4. Write the form-check class and its parts on the result line

Kind: behavior. Reads: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/job_result.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/refine/test_roadmap_refine_job_result.py`, `tests/roadmap/test_roadmap_faults.py`, `tests/roadmap/refine/test_roadmap_refine_alert.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/refine/test_roadmap_refine_job_result.py`, `tests/roadmap/test_roadmap_faults.py`.

- [x] 4.1 `test_a_form_check_failure_writes_its_class_and_its_parts_on_the_result_line` in `tests/roadmap/refine/test_roadmap_refine_job_result.py`: it runs a round whose first criterion has an empty `then` and asserts that the result line holds `class=form_check` and `failed_1=acceptance_criteria.0.then`, and it runs a round whose failure holds a form check beside an open question and asserts `class=form_check`; `test_the_classes_are_the_twenty_one_of_the_taxonomy` and `test_the_default_actions_are_the_ones_of_the_design` in `tests/roadmap/test_roadmap_failure.py` expect `form_check` and `retry`; `test_every_failure_class_has_a_fault_case` in `tests/roadmap/test_roadmap_faults.py` allows `form_check` as the one class with no case
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/refine/test_roadmap_refine_job_result.py tests/roadmap/test_roadmap_faults.py` fails on the base
- [x] 4.2 Add the member `FORM_CHECK` with the value `form_check` to `FailureClass` in `src/devops_cli/roadmap/failure.py`, and the action `retry` for it to `ACTION_BY_CLASS` in the same file. In `_log_attempt` in `src/devops_cli/roadmap/refine/refine.py`, pass the new class when the round's failure holds `JobCheck.ACCEPTANCE_CRITERIA`, `JobCheck.PROBLEM_STATEMENT` or `JobCheck.EXISTING_TOOL`, and pass each part that `form_check_details(result.proposal)` gives through the `names` argument of `log_job_result` as `failed_1`, `failed_2` and so on, with its brackets written as dots. Add `form_check` to the expected set and to the default-action table of `tests/roadmap/test_roadmap_failure.py`, and drop the count from the name of the class-set test there. In `tests/roadmap/test_roadmap_faults.py`, compare the case classes with the taxonomy without `form_check` and say in the docstring that only the refine round records it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py tests/roadmap/refine/test_roadmap_refine_job_result.py tests/roadmap/test_roadmap_faults.py` passes

## 5. Describe the failure detail and the class in the documents

Kind: other. Reads: `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/roadmap/refine.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 Update the form-check bullet and the rows of `refine.failure` and `refine.judge_findings` in `docs/roadmap/refine.md`, and the refine rows of `docs/ROADMAP_WORKFLOW.md`, to name the criterion index and part of a form-check failure, the whole failure that the next request carries, and the class `form_check` of the result line. Drop the sentence and the row text that name the removed character caps
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/roadmap/refine.md` and `docs/ROADMAP_WORKFLOW.md` to name the criterion and part of a form-check failure, the whole failure that the next request carries, and the class `form_check` of the result line
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
