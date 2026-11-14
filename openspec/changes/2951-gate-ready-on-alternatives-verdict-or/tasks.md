# Tasks

## 1. Gate Ready on the alternatives verdict

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_covers_check.py`, `tests/roadmap/refine/test_roadmap_refine_next_step.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` (new).

- [ ] 1.1 Write `test_an_item_with_no_verdict_stays_new` in `tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` first, beside the existing covers test `test_a_covers_check_with_no_reply_is_a_question_for_a_person_the_model_cannot_answer` in `tests/roadmap/refine/test_roadmap_refine_covers_check.py`: a public store, an item with no `alternatives.verdict`, and a Ready proposal give the next step `alternatives`, no Ready, the label `status/new` and a comment that holds `Waiting for the alternatives check to run.` A second case renders the plan of that item and asserts that the report holds the heading of the new step
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` fails on the base
- [ ] 1.2 Add `alternatives_gate(check, *, on)` to `src/devops_cli/roadmap/refine/refine.py`: it returns true when `check` is not None or `on` is false. Add the member `ALTERNATIVES = "alternatives"` to `NextStep`. In the round, keep `check_ready` in `proposal_ready`, set `gate = alternatives_gate(recorded_check(item, current_body), on=web.on)`, and set `is_ready = proposal_ready and gate`. After `next_step_of`, set the step to `NextStep.ALTERNATIVES` with no details and no blockers when `proposal_ready` holds and `gate` fails. Add `case NextStep.ALTERNATIVES: return None if recorded_check(item, item.body) is not None else _settled_wait(item, step)` to the match of `_still_waiting`. In `src/devops_cli/lang/en/messages.py` add the key `alternatives` to each of the three maps that a step value indexes: `refine_step_comments` with the text `Waiting for the alternatives check to run. The next refine round looks at the item again after the check records a verdict.`, `refine_left_waits` with `The item waits for the alternatives check to run. {details}`, and `refine_step_headings` with `## Waiting for the alternatives check`. The new test file also holds a case for each of the verdicts `none`, `not-applicable`, `rejected` and `in-use`, one for a private store, and one that asserts that each of the three maps holds the key `alternatives`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` passes

## 2. Leave a person's Ready label alone

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/status_sync.py`, `tests/roadmap/refine/test_roadmap_refine_covers_check.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py`.

- [ ] 2.1 Write `test_a_person_set_ready_survives_a_round_with_no_verdict` in `tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` first, beside the existing tests of `src/devops_cli/roadmap/refine/refine.py` in `tests/roadmap/refine/test_roadmap_refine_covers_check.py`: an item whose Status label is Ready, whose job record holds the Status New, and whose record holds no verdict keeps `status/ready` after one round and gains no other Status label
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` fails on the base
- [ ] 2.2 In `src/devops_cli/roadmap/refine/refine.py:def _apply_refined`, change the branch that takes an item whose Status label is Ready so that it also requires `owns_status(r.item)`; an item whose Ready label a person set then falls to the branch that writes the marks and the body alone, with no Status write. Add `owns_status` to the import at `src/devops_cli/roadmap/refine/refine.py:231:from devops_cli.roadmap.status_sync import StatusFacts, write_status`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_alternatives_gate.py` passes

## 3. Give the public-repository refine tests a recorded check

Kind: other. Reads: `tests/roadmap/refine/test_roadmap_refine_covers_check.py`, `src/devops_cli/roadmap/stores/store.py`, `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`. Changes: `tests/roadmap/refine/test_roadmap_refine_investigation.py`, `tests/roadmap/refine/test_roadmap_refine_deferred.py`.

- [ ] 3.1 Update `test_a_fact_that_a_file_read_settles_makes_the_item_ready` and `test_a_round_on_a_public_repository_with_a_key_settles_a_fact_from_the_web` in `tests/roadmap/refine/test_roadmap_refine_investigation.py`, and `test_deferred_a_complete_proposal_plans_one_new_issue_for_each_part` in `tests/roadmap/refine/test_roadmap_refine_deferred.py`: each item that the round takes gets the block and the `alternatives.verdict` key `none`, through a local copy of `_record_check` from `tests/roadmap/refine/test_roadmap_refine_covers_check.py`, or the store seeds private where the test is about another rule. Keep every assertion of each test. Run `uv run devops ci test tests/roadmap/refine` and give the same recorded check to each other test module of that folder that the run names
  - Verification: `$ uv run devops ci test tests/roadmap/refine` passes

## 4. Name the gate in the workflow document and run the whole gate

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [ ] 4.1 Add the rule to the step 2 row of the eight-steps table of `docs/ROADMAP_WORKFLOW.md`: refine sets `status/ready` only when the job record holds an `alternatives.verdict` or the alternatives check is off for the repository, and an item with no verdict waits for the check. Keep the columns and the links of the row. Then run the whole gate of the branch, which runs the docs row of `uv run devops ci` too
  - Verification: `$ uv run devops ci` passes
- [ ] 4.2 Edit `docs/ROADMAP_WORKFLOW.md` step 2 of the eight steps to name the alternatives-verdict gate
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: A test shows an item with no verdict stays New, and runs with a verdict or an exempt class.
- Group 2: A person can set Ready by hand, and refine does not revert it.
- Group 4: The workflow document names the rule.
- Group 4: `uv run devops ci` passes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
