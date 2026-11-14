# Design

## Decisions
- **Set the flag on both groups.** A fallback sends the same request to the second group, so both groups take the same `response_format`.
- **Hold it with a test.** The fallback test compares the flag of both groups, so a later move of a line fails CI.

## Rejected alternatives
- **Remove the flag from the fallback group.** A call that falls back would then lose its structured reply.
