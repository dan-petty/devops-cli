# Proposal

## Why

Issue #3215 asks the stage job and the implement job to build the text of their pull requests with `pull_form`, the one module of the rules (#3198), so that a pull request of the Service obeys the rules that `devops pr create` enforces for a person. The issue text is older than the code. At the staging commit, `staging_title` and `delivery_title` already use `pull_form` and cut nothing (#3200, #3249), and `SUMMARY_MAX_CHARS` is read from `pull_form` only. Two gaps remain:

- The implement job cuts the "why" with `textwrap.shorten(..., placeholder="...")`, and it writes the body in the order `Closes #N`, why, `Change:`. A cut text ends with `...`, and the order breaks the form of `body_problems`. The job never checks the body.
- The stage job formats its plan body with a message template in `stage_change.py`. `pull_form` checks a plan body (`plan_body_problems`) but does not build one, so the stage job never checks its plan body.

## What Changes

- `pull_form` gains `build_plan_body(why=, issue=, change=)`. It builds `Plans #<issue>`, the text and the `Change:` line, and raises `ValidationError` with every problem of `plan_body_problems`. The delivery form keeps refusing a body with no `Closes` line.
- The stage job builds its plan body with `build_plan_body`. A refused body goes back to the model with the other problems of the reply, as the job does for a refused plan (one return), and the second refusal stops the item with the existing failure of a refused reply. The job writes no body that fails the form.
- The implement job builds its body with `build_body`, in the order text, `Closes #N`, `Change:`. The text is the "Why" of the archived proposal when it fits in the room that the body limit leaves and holds no closing keyword. Otherwise it is the title of the issue. A body that `build_body` refuses stops the item before the job writes it, as a refused title does. The job calls `textwrap.shorten` for no title and no body.
- The messages `implement_pull_body` and `stage_pull_request_body` go, and one message names a refused implement body.
- Left to other issues: the retry of a refused implement body by the model (#3599) and the call of `body_problems` by `devops pr check-readiness` (#3259). The implement job has no free-text model step for the body, so a retry there needs a new prompt and step.
- Observable: the body of a pull request that the implement job writes has a new order, and a refused body stops the item. The change adds a delta to `pull-request-form`, `roadmap-implement-job` and `roadmap-stage`.
- The change fits one pull request.

## Impact

- `src/devops_cli/roadmap/pull_form.py`, `stage_change.py`, `stage.py`, `implement_run.py` and `src/devops_cli/lang/en/messages.py`.
- `tests/roadmap/test_roadmap_pull_form.py`, `test_roadmap_implement_job.py`, `test_roadmap_stage_prompt_rules.py` and the stage tests that read the plan body.
- Code deleted: the `textwrap.shorten` call of `_why`, the message `implement_pull_body`, the message `stage_pull_request_body`.

## Feasibility

Checked on `origin/main` 26a0ef46, 2026-11-06, by reading the code.

- `git grep -n "textwrap.shorten" src/devops_cli/roadmap/implement_run.py` finds one call, in `_why`. `git grep -n "textwrap" src/devops_cli/roadmap/stage_change.py` finds nothing. So the claim of the issue that the stage titles are cut is false, and the work is the implement body and the stage plan body.
- `staging_title` raises `RoadmapStageError` over `SUMMARY_MAX_CHARS`, and `delivery_title` keeps the whole summary. Both stay as they are.
- `plan_body_problems` exists and accepts `Plans #<issue>`; no builder exists. The text between `Plans` and `Change:` must have at least 20 characters, which `StageProposal.pull_request_body` (1 to 800 characters) can break. The stage job returns such a reply to the model once through the path that `_gated` already has, so the job needs no new retry code.
- The implement job has no model call for the body. Its "why" comes from the archived proposal or the issue title, so a refused body stops the item, as a refused title does (`_delivery_title`).
- The draft body of the first push (`implement_pull_body_draft`) is a stand-in that the final body replaces; the rewrite after the push is the body that the squash commit takes. This change leaves the draft as it is.

## Existing Tool Considered

The alternatives check of 2026-11-05 found no tool that builds a title and a body with `Closes` or `Plans`, `Change:` and attribution under a character bound: commit and title linters, Commitizen and static templates do not. The project module `pull_form` holds the rules, and this change only calls it. Cost to build and keep: about 80k tokens and 4 hours to build; nothing new to keep, because the rules have one source.
