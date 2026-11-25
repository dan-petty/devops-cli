# Proposal: #6445

## Why
Refine turns post-merge timing, merge ownership, and post-release live-proof checks into `person` key questions, leaving items stuck in `New` (`refine.next_step = person`) even though an agent never merges a PR and post-merge or post-release steps do not alter the pre-build design.

## What Changes
- Remove `a merge` from the `person` decision list in `src/devops_cli/ai/tasks/roadmap_refine_reply.md` and direct post-merge / post-release live-proof checks to an acceptance criterion named `Pending a person after the merge`.
- In `src/devops_cli/roadmap/refine/refine.py` (`validate_proposal`), convert any `person` question that asks when/who merges a pull request, record, ADR, change, or draft — or who runs or confirms a live proof or check after the merge or release — into the acceptance criterion `Pending a person after the merge` with no open question, while keeping pre-build `person` questions (such as a secret, repository setting, or host) open.
- Bump `CONST_ROADMAP_REFINE_RULES_SINCE` in `src/devops_cli/config/constants.py` and document the new rules date in `docs/roadmap/refine.md`.
- Update `tests/roadmap/refine/test_roadmap_refine_proposal.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`, and OpenSpec `roadmap-refine/proposal`.

## Capabilities

### Modified Capabilities
- `roadmap-refine/proposal`: remove `a merge` from the `person` list in `roadmap_refine_reply.md`, instruct writing post-merge steps as `Pending a person after the merge`, convert post-merge merge and post-release live-proof `person` questions deterministically in `validate_proposal`, keep pre-build `person` questions open, and advance `CONST_ROADMAP_REFINE_RULES_SINCE`.

## Impact
- `src/devops_cli/ai/tasks/roadmap_refine_reply.md`
- `src/devops_cli/roadmap/refine/refine.py`
- `src/devops_cli/config/constants.py`
- `docs/roadmap/refine.md`
- `tests/roadmap/refine/test_roadmap_refine_proposal.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`

## Feasibility
Confirmed on `origin/main`: `roadmap_refine_reply.md:9` lists `a merge` under `person`, `validate_proposal` (`refine.py:1663-1665`) leaves every `person` question open, `stage_criteria.py:38` handles `pending-person`, and `CONST_ROADMAP_REFINE_RULES_SINCE` (`constants.py:3659`) re-triggers older person waits.

## Existing Tool Considered
The alternatives check of 2026-11-19 recorded `none`. No external library maps this repository's `person` question vocabulary to `Pending a person after the merge`; cost is about 40k tokens and half a day to build.
