# Proposal: #5465

## Why
`collect_context` in `src/devops_cli/roadmap/refine/refine.py` includes the full text of the first five files in `docs/adr/` for every stage, fix-plan, and refine item. That includes superseded ADRs (0002 and 0003) and uses nearly 5k tokens ahead of cited source files, causing cited files to be truncated at the token cap.

## What Changes
- Replace the first five full ADR files in `collect_context` (`src/devops_cli/roadmap/refine/refine.py`) with a single section holding one heading instructing `read_file` on `docs/adr/` and sorted `ADR NNNN: <title>` index lines for every ADR in force at the staged commit (`adr_of` and `Adr.in_force`).
- Emit no ADR index section when no ADR is in force at that commit.
- Update and add context and trace-gate tests in `tests/roadmap/refine/test_roadmap_refine_context.py`, update the stub context token count in `tests/roadmap/refine/test_roadmap_refine_job_result.py`, and use `CONTEXT.md` to saturate context budgets in `tests/roadmap/stage/test_roadmap_stage_window.py`.

This change alters the observable context built for stage and refine jobs, so it adds a requirement to `roadmap-refine/context`. It fits one pull request.

## Capabilities
- `roadmap-refine/context`: replace full initial ADR texts with a sorted one-line index of ADRs in force.

## Impact
- Frees roughly 4.4k tokens inside the stage and refine context budget for cited source files while excluding superseded ADRs.
- Leaves the trace gate unchanged so an ADR named only in the index still requires a `read_file` span.

## Feasibility
Confirmed against `origin/main` source (`src/devops_cli/roadmap/refine/refine.py:1058-1117`, `src/devops_cli/roadmap/adr.py:115-203`) and `openspec/specs/roadmap-refine/context/spec.md`.

## Existing Tool Considered
`adr_of` and `Adr.in_force` in `src/devops_cli/roadmap/adr.py` already parse front matter, titles, and in-force status (`accepted` or None with empty `superseded-by`). Reusing them adds no new parser or external tool at roughly 0.4M tokens and 1 hour to build.
