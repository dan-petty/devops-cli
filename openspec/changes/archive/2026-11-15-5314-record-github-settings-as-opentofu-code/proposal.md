# Proposal

## Why

No record said where the repository and organization settings live, who changes them, or how a person verifies a transfer. The plan of #5311 moves repositories, and three designs competed (#5314).

## What Changes

- Add `docs/adr/0026-github-settings-live-in-opentofu-code-and-the-owner-applies-it.md` with MADR front matter. It records owner decisions 1, 4, 5 and 7 of #5311, the two stacks, the Kubernetes backend in `tofu-state`, the read-only App that plans, the owner who applies, the scope split, postconditions in place of checks, the unmanaged `main` ruleset, the import-only plan of a transfer, and the rejected alternatives.
- Regenerate the ADR index.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. An ADR records a decision.

## Impact

- Documents: `docs/adr/0026-...`, `docs/adr/README.md`

## Feasibility

- Read on `origin/main`, 2026-11-15. `docs/adr/README.md` holds the form and the front matter fields.
- `uv run pytest tests/docs/test_docs_adr_records.py` passes with the new record and its body hash.

## Existing Tool Considered

MADR, the ADR format of `docs/adr/`.

## Dependencies

Owner decisions 1, 4, 5, 7 in #5311, decided 2026-11-13.
