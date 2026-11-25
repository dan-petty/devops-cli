# Proposal: #6523

## Why
`_still_waiting` in `src/devops_cli/roadmap/refine/refine.py` checks `_set_by_older_rules` only in the `NextStep.PERSON` path (`_person_wait_over`, `#4795`). Narrower dependency rules (like `#6451`) bump `CONST_ROADMAP_REFINE_RULES_SINCE`, but items recorded as `NextStep.BLOCKED` under older rules keep waiting on false blockers until closed, commented, or edited (`docs/roadmap/refine.md:33`).

## What Changes
- End a `NextStep.BLOCKED` wait in `_wait_still_on` (`src/devops_cli/roadmap/refine/refine.py`) when `_set_by_older_rules(item, since)` is true, giving the item one new look under the current rules and recording `CONST_ROADMAP_REFINE_RULES_SINCE`.
- Update `docs/roadmap/refine.md` so the rules-version paragraph states that a rule change ends a blocked wait as well as a wait on a person.
- Add tests in `tests/roadmap/refine/test_roadmap_refine_person_wait.py` proving an older-rules blocked wait re-evaluates, a current-rules blocked wait stays waiting, and a real dependency remains blocked under the current rules.

## Capabilities
- `roadmap-refine/waits`: End recorded `NextStep.BLOCKED` waits when older refine rules recorded them.

## Impact
- `src/devops_cli/roadmap/refine/refine.py`
- `docs/roadmap/refine.md`
- `tests/roadmap/refine/test_roadmap_refine_person_wait.py`

## Feasibility
Confirmed against `origin/main`:
- `_still_waiting` (`refine.py:2956-3018`) sets `names_cause = step is NextStep.PERSON` and calls `_person_wait_over` (which calls `_set_by_older_rules`) only when `names_cause` is true.
- `docs/roadmap/refine.md:33` currently states: `The new version ends no blocked wait: an item keeps its recorded blockers until none is an open blocker, a person replies or a person edits the body.`
- Issue `#6451` is closed and merged into `origin/main`.

## Existing Tool Considered
No external tool covers refine's internal `NextStep.BLOCKED` wait cursor. Reusing `_set_by_older_rules` in `_wait_still_on` keeps one helper and zero new record keys (~3k tokens, under 1 hour).
