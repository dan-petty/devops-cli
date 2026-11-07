# Design

## Overview

`SECURITY.md` owns the rule, because AGENTS.md says that each rule lives in one document. `AGENTS.md` rule 5 holds one clause with a link to the section, so the exception shows where the rule is. `docs/ROUTINE_TASKS.md` holds the routine that the rule creates (renew or drop), and points to the section.

## Decisions

- The heading is "A Finding with No Fix". `AGENTS.md` has a limit of 6,500 characters, so a short anchor keeps the clause short.
- The 3 days apply to every automatic entry. An entry that the owner names with another date, such as the 14 days of #3881, keeps that date.
- The 14-day total counts from the first entry. After it, the agent stops and asks, because a longer ignore is the owner's decision.
- The expiry is the only reminder. The scan fails after the date, so the rule adds no scheduler.

## Rejected Alternatives

- **Copy the rule into `AGENTS.md`**: the file is at its character budget, and AGENTS.md says that each rule lives in one document.
- **A new invariant for the 3-day limit**: the entry holds the end date and not the start date, so no offline test can compute the limit.
- **Lift the CRITICAL limit**: the owner kept it, and an agent asks for a CRITICAL finding.
