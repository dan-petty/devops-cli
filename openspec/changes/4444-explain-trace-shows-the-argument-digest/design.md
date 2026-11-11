# Design

## Decisions

- The digest goes after the program and before the outcome, in square brackets: `tool shell (program git) [argument abc123abc123], ok`. The digest names the call, so it stands with the tool and the program. The outcome, the exit status and the reason stay at the end, as before.
- The word `argument` tells the reader what the hexadecimal value is. The value is the digest of the masked argument, not the argument.
- The part is empty when the event holds no digest, the same as the program part. An old trace or a hand-made trace with no digest still prints.

## Rejected alternatives

- Change the requirement "The trace option prints the trace of the last run". Its text is near the 500-character limit of `openspec validate --strict`, so a new requirement holds the digest.
- Show only the first characters of the digest. The digest is already 12 characters, and a shorter value makes two different calls look the same.
