# Design

## Decisions
- Build the ADR index inside `collect_context` (`src/devops_cli/roadmap/refine/refine.py`) by reading files under `docs/adr` at `sha`, parsing each via `adr_of` (`src/devops_cli/roadmap/adr.py:189`), filtering on `adr.in_force`, sorting by `adr.number`, and emitting one heading plus `ADR NNNN: <title>` lines only when at least one ADR is in force.

## Rejected alternatives
- Parse front matter again in `refine.py`: rejected because `adr_of` and `Adr.in_force` in `src/devops_cli/roadmap/adr.py:116-203` already own ADR status and title extraction.
- Keep emitting an empty heading when zero ADRs are in force: rejected because an empty index wastes tokens and directs the planner to `docs/adr/` when none is active.
- Treat index entries as read in `TraceFacts`: rejected because the planner has not read the full ADR body without calling `read_file`.
