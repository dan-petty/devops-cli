# Proposal

## Why

Release pull request #5690 failed the `Static Analysis` quality gate because of an OpenSpec requirement overlap (#5692). Both #3148 and #5451 rewrote the requirement "The prompt lists the local devops commands of the catalog" in `roadmap-implement-step/inputs`. PR #5587 (for #5451) and PR #5635 (for #3148) merged independently into `main` without checking the overlap.

## What Changes

- Change 3148 adds "The code-intelligence commands of the catalog are read-only" as an `ADDED` requirement instead of modifying "The prompt lists the local devops commands of the catalog".
- This change resolves the overlap while keeping the specification additions of #3148.
- The change alters no runtime code or behavior a consumer observes, so it sets `skip_specs: true` in `.openspec.yaml`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Specifications: `openspec/changes/3148-give-the-implement-agent-read-only/specs/roadmap-implement-step/inputs/spec.md`, `openspec/changes/3148-give-the-implement-agent-read-only/proposal.md`

## Feasibility

- Running `uv run devops ci --only openspec` confirms the overlap before the change and verifies that the gate passes after the change.
- Verification command: `uv run devops ci --only openspec`.

## Existing Tool Considered

`devops openspec check` and OpenSpec tools enforce the consistency. No new tool is necessary.
