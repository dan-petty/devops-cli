# Design

## Decisions

### 1. Widen applies_to to major wildcards
- **Decision**: Set `pkg:pypi/pydantic-ai@2.*` and `pkg:pypi/pydantic-ai-harness@0.*`.
- **Rationale**: Follows repository convention used by `pydantic@2.*`, `packaging@26.*`, and `rich@15.*`. Avoids false drift failures on minor and patch dependency bumps.

## Rejected alternatives

### 1. Update pattern on every minor dependency release
- **Rejected**: Forces manual synchronization commits on every automated Renovate PR, creating unnecessary toil.
