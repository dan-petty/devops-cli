# Tasks

## 1. Add the missing-check claim search to the premise probe

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/roadmap/premise.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`. Changes: `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_probe.py`.

- [x] 1.1 Write `test_a_check_in_a_helper_body_of_the_call_site_is_found`, `test_a_check_that_only_another_file_holds_names_its_path_and_line`, `test_a_claim_with_no_call_site_adds_no_line` and `test_a_claim_with_no_command_left_is_skipped` in `tests/roadmap/stage/test_roadmap_stage_probe.py` first
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py` fails on the base
- [x] 1.2 Add to `src/devops_cli/roadmap/stage/stage_probe.py`: `claimed_missing_checks(texts)` reads each line that holds an absence word before the word check or guard and the code span of the named check on either side of that word, takes the other code-spanned identifier of the line as the call site, and returns each pair once. `check_claims(source, sha, claims, left)` starts a `_Run` with the commands left, and for each claim reads the definition of the call site with `definition_lines` and `commands=self.left`, reads that file once with `git cat-file -p <sha>:<path>`, searches the body of the call site and the body of each function that body calls in the same file, then searches `SYMBOL_PATHSPECS` with one `git grep -n -w`, and appends the message `stage_probe_claim_found` with the path and the line of the check to `false_premises`. A claim with no command left goes to `skipped`, and a search that does not finish adds no line. Add the `left` field to `Probe` and set it from `run.left` in `probe_premise`, the helpers `_functions` and `_callees`, the export of both new functions, and the message to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_probe.py` passes

## 2. Return the item when a plan claims a check that the base holds

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_probe.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 2.1 Write `test_a_plan_that_claims_a_missing_check_in_a_helper_returns_the_item` and `test_a_plan_that_claims_a_missing_check_that_the_base_lacks_stays_ready` in `tests/roadmap/stage/test_roadmap_stage_plan.py` first. The first seeds `_publish`, `_delivery_title` and `title_problems` in the sample file with `advance_origin` and asserts the comment, the `FalsePremise` kind and `refine.next_step`; the second asserts that the plan stays ready and records no premise
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` fails on the base
- [x] 2.2 Add `PremiseKind` with `ABSENT_FIELD` and `MISSING_CHECK`, and the `kind` field of `FalsePremise` with `ABSENT_FIELD` as its default, to `src/devops_cli/roadmap/stage/stage.py`. Keep the commands that the probe has left on `_Planner`, and add `_Planner._claim_premise`, which calls `claimed_missing_checks` on the texts that `_settle` builds and `check_claims` on the staging commit with those commands, and call it first in `_settle`, whose result becomes `StagedChange | OverBudget | FalsePremise | _Refused`. Widen the return type of `_gated`, `_returned` and `_note_gates`, and return `PlanRevision(premise)` for a `FalsePremise` in `revise`. In `_return_premise` pick `stage_returned_claim` with `NextStep.RETRY` for `MISSING_CHECK`, and in the run report pick `stage_returned_claim_line`. Add both messages to `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
