# Design

## Decisions
- Move `_ISSUE_REF_RE` from `src/devops_cli/roadmap/refine/refine.py` into `src/devops_cli/roadmap/body_hash.py` as `ISSUE_REF_RE` and `issue_references(text)` because both `refine.py` and `intake.py` already import `body_hash.py`, avoiding circular imports or duplicate regexes.
- Add `apart: Collection[int] = ()` on `NewCandidate` and pass `frozenset((item.number, *_recorded_numbers(item)))` from `_plan_deferrals` so refine deferrals keep `source=None` (no sub-issue link) while skipping comparison against the parent and previously filed deferrals.
- Keep `_priority` returning `f"{proposal.priority_reason} {granted}".strip()` on P0 grants (matching P0 refusals) and append `(ItemField.PRIORITY.value, "", priority[1])` only when `priority[1]` is non-empty, formatted with `MESSAGES.roadmap.intake_comment_field_reason` (`"- {field}: {reason}"`) so no label value or trailing extra dot appears.
- Drop `\n- After: \`{new}\`` from `retitle_comment_changed` and `retitle_comment_type_changed` in `messages.py` and remove the `new=change.title` format argument in `retitle.py`.

## Rejected alternatives
- Setting `source` on refine deferrals: rejected because that would create sub-issue links and change tracker semantics on the parent item.
- Filtering `Possible duplicate: #N` when the body cites `#N`: rejected because duplicate flags must never be suppressed (`flag, never drop`).
- Adding a second `#N` regex inside `intake.py`: rejected because two parsers can drift on edge references.
