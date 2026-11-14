# Design

## Context

`_criteria` reads `- Pending person: <criterion>, <reason>` and splits at the first `, `. The issue's acceptance criteria are available later in `criterion_problems`, not in the reader.

## Goals

- Map a criterion with a comma to its whole text.
- Keep a reason with a comma.
- Report a pending-person entry that matches no issue criterion.

## Decisions

- **Resolve in `criterion_problems`.** It holds both the parsed entries and the issue's criteria. The joined text starts with an issue criterion and a comma when the split was wrong. The longest match wins, so a prefix does not cut a longer criterion.
- **No change to the line form.** Old plans keep their form, and the resolution only fills a text the issue already states.

## Risks

- A criterion and a reason that together equal a longer issue criterion resolve to that criterion. That text is the issue's own criterion, so the mapping is correct.

## Tests

- A criterion with a comma maps to the whole text.
- A reason with a comma keeps its whole text.
- The longest of two prefix criteria wins.
- An entry that matches no issue criterion is still reported.
