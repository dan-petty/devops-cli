# Proposal

## Why

Refine puts an item in the group "waits on a person" when no person has a decision to make (#3632). On 2026-11-05 at about 14:00Z, 56 New items of this repository were in that group, and none had a reply. The last refine comment of 21 of them held only `(missing verified source)` questions, which the read tools of the investigation can answer. The last comment of 16 of them held the text "The proposal has no problem statement", which is a form check that the model reply failed. Eight investigations in 14 hours ended with `Exceeded maximum output retries (2)`, and each one kept the open questions of its item. Only 13 of the 56 items held a question marked `(a person decides)`. A person cannot act on the other 43. This change makes a person wait only for a decision.

## What Changes

- A reply that fails the form check of `check_ready` (no problem statement, no answer to the existing-tool question, no complete acceptance criterion) is a job failure. `src/devops_cli/roadmap/refine.py` gets `form_checks`, which names each failed check, and `check_ready` uses it.
- An open question that is not marked `(a person decides)` after the investigation is a job failure, not a person wait. This covers `(missing verified source)`, a body question that no answer names, and a question that stays open when the investigation stopped (`Exceeded maximum output retries (2)`, or a spent budget). The investigation already answers such a question with the read tools. `InvestigationTools` now keeps the list of what it searched, and the job failure says what the tools searched when they found nothing.
- A job failure writes no body and no comment. The job record of the item counts the tries (`refine.tries`), names the failed checks (`refine.failed_check`) and keeps the last error (`refine.failure`). The new next steps are `retry` (a later round tries again) and `failed` (the limit `CONST_ROADMAP_REFINE_MAX_TRIES`, 3, is reached; only a body edit ends the wait). A body edit sets the count to 1 again, and a proposal that passes clears the three keys.
- `devops roadmap inbox` lists an item whose next step is `failed` in a new class `failed`, with the failed checks, the try count and the last error. It lists no `retry` item and shows no question for either.
- A question marked `(a person decides)` still makes the item wait on a person. A job failure comes before it: a proposal that is not valid asks no person.
- The refine plan report counts the items that go on without a person (ready, blocked, retry) and lists each one.
- `devops roadmap explain` names the two new next steps.
- The change carries spec deltas: the report, the inbox class, the explain text and the job record are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-refine`: A stopped investigation keeps the first proposal, Only a person's decision waits on a person, A form check failure is a job failure that retries, A job failure at the try limit waits on a body edit, A source question is answered with the read tools or reports what they searched, The report counts the items that go on without a person
- `roadmap-inbox`: The inbox lists each item whose refine job failed at the try limit
- `roadmap-explain`: Explain names a refine job failure

## Impact

- Code: `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/store.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/inbox_kind.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/roadmap/refine.md`, `docs/roadmap/inbox.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/commands/roadmap.md`, `docs/CLI_REFERENCE.md`, `README.md`
- Tests: `tests/roadmap/test_roadmap_refine_job_failure.py` (new), `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_refine_investigation.py`

## Feasibility

- `read_file src/devops_cli/roadmap/refine.py` (`origin/main` at c7145511, 2026-11-06) confirms the cause. `next_step_of` gives the step `person` to every proposal that is not ready, and its last line gives `MESSAGES.roadmap.refine_incomplete` ("The proposal has no problem statement, no acceptance criterion with its requirement, ...") as the only detail when `check_ready` fails with no question, split, block or suspected block. That is the text on the 16 items. `validate_proposal` adds `(missing verified source)` to a fact with no valid source, and `next_step_of` sends every open question to a person. So the premise holds for the form check and for the source question.
- `read_file src/devops_cli/roadmap/refine_investigation.py` shows that `investigate` returns `InvestigationStopped` for `UnexpectedModelBehavior`, which carries `Exceeded maximum output retries (2)`. `_investigate` turned that into `None`, and `refine_one_item` kept the first proposal with its open questions. The spec requirement "A stopped investigation keeps the first proposal" states this. So the premise holds for the output retry, and the change replaces that requirement.
- The investigation already runs for a question with no verified source (`needs_investigation`, #2398), with `search_code`, `list_files` and `read_file` on the pinned commit. The issue text says "Refine answers a source question with its read tools before it asks". That part is true on `main`. The gap is that a question the tools could not answer still became a person wait, and that the run kept no record of what the tools searched. This change adds the record and the job failure, not a new tool.
- The counts of the issue (21, 16, 13, 6) come from the issue text and were read on 2026-11-05. The live data changes each hour, so a read of it is in a comment of the pull request, not here. That read is an estimate from the text of old comments. It is not a run of refine.
- The items that already hold the step `person` in their job record are not read again by this change. `_still_waiting` keeps an unchanged item in its recorded wait until a reply, a body edit, or a change to an issue or a file that the wait names. A new round with the new rules reaches such an item only after one of these, or with `devops roadmap refine --item <number>`. So the merge does not move the existing stale items. A one-time action for them is a separate item.
- A try limit that is "configurable" in the design of the issue is a constant here, as the other refine limits are (`CONST_ROADMAP_REFINE_MAX_COMMENTS_PER_ITEM`). A test patches it. A setting needs a key in the config model and in the generated reference for one number that nobody has asked to change.

## Existing Tool Considered

The change uses the read tools of the refine investigation and pydantic-ai output retries, which exist. No outside tool counts tries of a job in a GitHub issue record or lists a job failure in the inbox of this project, so the change extends `refine.py`, `inbox.py` and the job record. It adds no tool and no store. It removes the requirement "A stopped investigation keeps the first proposal" and the fall-through step `person` with the detail `refine_incomplete`. Written cost: about 45,000 tokens to build, about 5,000 tokens each year to keep and fix, and about 3 hours of elapsed time.
