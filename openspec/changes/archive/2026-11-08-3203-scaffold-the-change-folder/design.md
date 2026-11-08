# Design

## Decisions
- Derive slug with `slug_from_title` in `src/devops_cli/git/branch_form.py` so worktree creation and change folders share one slug.
- Gate unfilled scaffold lines with the replacement marker in `src/devops_cli/openspec/gate.py`.
- Keep templates deterministic and free of timestamps (delegating `created` date to `openspec new change`).

## Rejected alternatives
- Separate shell script for scaffolding: Rejected because it cannot reuse CLI error handling, telemetry, and GitHub rate limiting.
- Relying on manual author editing with no gate: Rejected because unfilled placeholders repeatedly slipped through code review.
