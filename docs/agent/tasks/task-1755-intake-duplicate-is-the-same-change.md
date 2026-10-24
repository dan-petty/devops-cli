# Task: Intake Calls a Candidate a Duplicate Only When It Asks for the Same Change (#1755)

**Issue**: [#1755](https://github.com/dan-petty/devops-cli/issues/1755)
**Scope**: scope/roadmap
**Feasibility**: Confirmed against the code at origin/main (a752a14a): `_resolve_raw` in `src/devops_cli/roadmap/intake.py` folded a candidate into any shortlist item the model named, and the reply carried only `duplicate_of` and a free reason. Confirmed against GitHub with read-only requests: the five folds of 2026-10-20 that #1755 lists, and the three duplicates a person closed with a comment that names the shared change (#1411 into #1418, #1375 into #1014, #454 into #452). The structured client appends the reply's JSON Schema to the system prompt and constrains the reply with it (`src/devops_cli/ai/client/structured.py`), so the new fields and their order reach the model.

## Description

Intake called a candidate a duplicate when it only shared a theme with an item, such as CI performance, dry runs or workflow friction, and then filed nothing. The criterion now lives in the prompt and in the reply schema:

- `roadmap_intake_system.md` defines a duplicate as the same change: the same result and the same acceptance criteria, so that the delivery of one item delivers the other. An umbrella item, a sibling, a neighbour and a defect in delivered work are new items.
- The reply names the change both items ask for (`shared_change`) before it names an original (`duplicate_of`). It can also name a related item that asks for a different change (`related_to`, `related_reason`).
- Code holds the reply to the criterion. An original named with no shared change is not a duplicate: intake places the candidate, names the original as related and adds a note. A related item off the shortlist is rejected with a note.
- A duplicate's reason, in the report and in the close comment, starts with the change both items ask for.
- A placed candidate with a related item gets a report line and a reason-comment line that names the item. The comment links the item, whose number code checked against the shortlist.
- CONTEXT.md defines **Duplicate** and **Related item**.

## Acceptance Criteria

- [x] Tests first: the evaluation set `tests/fixtures/roadmap/intake-duplicate-judgements.json` replays the model's answers of the five 2026-10-20 folds offline, through the shared model fake (`model_fake`) and `GatewayIntakeModel`. Each candidate is filed, and the report and the reason comment name the item as related (`test_a_candidate_that_shares_only_a_theme_with_an_item_is_filed_and_names_it_as_related`).
- [x] The set's three duplicates that a person closed are duplicates, and the reason names the shared change (`test_a_candidate_that_asks_for_the_same_change_is_a_duplicate_whose_reason_names_it`). Their answers are written from the person's close comment, not recorded from a model.
- [x] `roadmap_intake_system.md` defines a duplicate as the same change, and a duplicate decision carries a reason that names the shared change (`test_the_intake_prompt_defines_a_duplicate_as_the_same_change`, a snapshot of the prompt, and `test_a_duplicate_issue_closes_with_a_comment_that_names_the_shared_change`).
- [x] A related but distinct candidate is filed, and the report and the reason comment name the related item (`test_a_related_item_the_model_names_is_reported_and_linked_from_the_reason_comment`, `test_a_related_item_off_the_shortlist_is_rejected_with_a_note`).
- Pending a person: run `devops roadmap intake --title "fix(review): a review dry run starts no gh, and no child of a test reaches the real session bus" --body-file <file with the case's body> --plan`. The report shows no `duplicate of #1430` line.
- Pending a person: run `devops roadmap intake --title "fix(ai): response cache singleton ignores cache_enabled=False from later clients" --body-file <file with the case's body> --plan`. The report shows a `duplicate of` line whose reason starts with `both ask for`, such as a duplicate of #1014 or of #1375, which a person closed.

## Deliverables

- [x] The duplicate definition and the reply keys `shared_change`, `related_to` and `related_reason` in `src/devops_cli/ai/tasks/roadmap_intake_system.md`.
- [x] `ModelProposal` holds the new keys, with `shared_change` first (`src/devops_cli/roadmap/intake_model.py`).
- [x] Intake reads the reply into one judgement and places a candidate whose original has no shared change (`src/devops_cli/roadmap/intake.py`).
- [x] The report line, the reason-comment line and the notes in `src/devops_cli/lang/en/messages.py`.
- [x] The evaluation set, with each case's source.
- `devops ai prompt-eval` runs the evaluation set against the live model: moved to #1989. The command counts review verdicts today and calls no model.
