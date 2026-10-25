# Proposal

## Why

Issue #2218. The owner set false-positive duplicates of `devops roadmap intake` as a P0 on 2026-10-25.

Intake dropped a new candidate, and closed an existing issue, when the model named an original and a shared change. Nothing checked that the original asked for that change. Two false positives on 2026-10-25:

- A follow-up of the dashboard audit #1885, "delete the dashboard Kubernetes and Logs tabs; k9s replaces them", was judged a duplicate of #1885. #1885 is its umbrella: it asks for one follow-up issue for each tab that an open tool can replace. Intake filed nothing.
- "a review starts one sandboxed Gitleaks run for each file" was judged a duplicate of #1746, which asks that the CI Static Analysis job runs Bandit once. The "shared change" was a phrase of the candidate's title, which is not in #1746. Intake filed nothing and said "add to #1746 instead", and the agent posted its evidence on the wrong issue.

A dropped candidate is lost work, and a wrong close hides an issue. A missed duplicate costs one close by a person.

## What Changes

- A duplicate verdict of the model is a flag, never an action. Intake places a possible duplicate as it places any candidate: it files a new candidate, and it closes no issue. The report gives the line `  - possible duplicate: #<n>. The model names <change> as the change that both ask for. <reason>`, and the reason comment gives `- Possible duplicate: #<n>, which may ask for the same change. ... A person closes one of the two if that is so.`, which links the item.
- A new candidate whose title and body are those of an open issue that is not finished is that issue: a run that stopped after filing left it. Intake places that issue and files nothing. This exact match in code replaces the model verdict that found the issue before.
- These go, because only a duplicate close used them: `Outcome.DUPLICATE`, the held pairs, the duplicate comment and `CONST_ROADMAP_INTAKE_DUPLICATE_MARKER`, `IntakeApplied.closed`, `close_as_duplicate` of the store protocol, of the GitHub store (with its GraphQL mutation, `close_as_duplicate_request`, `_require_issue_node` and the issue payload's `node_id`) and of the memory store, the request plan's `close_as_duplicate`, the dry-run duplicate steps, and their messages.
- The check skips an issue whose timeline shows a duplicate close that a person reversed, as before.
- The help text of `devops roadmap intake`, its docstring, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md` and the knowledge base page on project management say that intake names a possible duplicate and never drops or closes. The generated command and MCP documents follow.
- The report, the reason comment and the writes are observable behaviour, so the change has a spec delta: the new capability `roadmap-intake-duplicates`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `roadmap-intake-duplicates`: what `devops roadmap intake` does with a candidate that the model judges a duplicate, and with a candidate that a stopped run already filed.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/roadmap/intake.py`, `intake_requests.py`, `request_plan.py`, `store.py`, `github_store.py`, `memory_store.py`, `run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py` and `help.py`.
- `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`, and the generated `README.md`, `docs/CLI_REFERENCE.md`, `docs/MCP_TOOLS.md` and `docs/commands/roadmap.md`.
- `tests/test_roadmap_intake.py`, `tests/test_roadmap_store_contract.py`, `tests/test_roadmap_github_store.py`, `tests/roadmap_board_fake.py`, `tests/roadmap_faults.py`.

## Feasibility

- The false positives: the two intake runs of 2026-10-25 above, with the reports that intake printed. The model's shared change for #1746 is a phrase of the candidate's title; `#1746` holds no word "Gitleaks".
- A check in code cannot make the verdict right. In `tests/fixtures/roadmap/intake-duplicate-judgements.json`, the shared change of each of the three true duplicates, which a person closed, is in neither the candidate's text nor the item's text, so a literal check would reject all three. A check that each side's quote is in its own text passes the #1885 case, because an umbrella holds real text that the model can quote.
- The owner chose "flag, never drop" on 2026-10-25 from these options.
- The retry of a stopped run: `test_a_retried_new_candidate_finds_the_issue_its_stopped_run_filed` relied on the model's verdict. The issue such a run files holds exactly the title and `NewCandidate.filed_body()` of the candidate, so code can match it with no model.

## Existing Tool Considered

GitHub's "Mark as duplicate" and close as duplicate stay a person's actions. No open tool judges whether two issues ask for the same change; the model's judgement stays, as a flag.

The change deletes the duplicate close and every path that only it used (listed above), about 300 lines of source and tests more than it adds.
