# Design

## Context

The post-merge audit needs one line that names the defect class and cites the issue. Section 7.4 of `ARCHITECTURE.md` already lists the stage and workflow rules that the roadmap follows, so the sentence belongs there.

## Decisions

- One bullet in the list of section 7.4. It describes the rule that the implement job applies to a plan, and it cites #3393.
- No new surface, no new check. The audit already reads the declared surfaces.
