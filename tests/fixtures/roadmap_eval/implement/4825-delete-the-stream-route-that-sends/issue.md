### Problem Description

The route `/stream/events` in `src/devops_cli/server/routes/stream.py` sends the canned text "Zero-trust security invariants verified. No unvalidated egress found." for any persona. Nothing runs before it sends that text. Only tests call the route.

### Reproduction Steps

1. Call `GET /stream/events` with any persona.
2. The feed says that checks passed, but no check ran.

### Expected vs Actual Behavior

- Expected: the server sends no claim that a check passed when no check ran.
- Actual: the route sends a canned "verified" claim.

### Proposed Solution

Delete the route, its persona allowlist (`DEFAULT_ALLOWED_STREAM_PERSONAS` and `DEFAULT_STREAM_PERSONA` in `src/devops_cli/config/defaults.py`), its wiring in `src/devops_cli/server/app.py` and its tests. Alpha keeps no compatibility, so add no shim. The owner accepted the delete on 2026-11-11 (#4780).

### Existing Tool Considered

A delete. No tool applies. Cost to build: about 20,000 tokens and 0.5 hours.

### Acceptance Criteria

- A search finds no reference to the route.
- The server tests pass.
- The API documents regenerate with no diff left.

### Dependencies

None.


Source: https://github.com/dan-petty/devops-cli/issues/4780

<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
