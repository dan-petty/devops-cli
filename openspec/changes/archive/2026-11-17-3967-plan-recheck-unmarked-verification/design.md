# Design

## Decisions

### Rewrite unmarked verification lines in place
Rewrite the line in place before `_verification` checks whether to add a command.
Prepend `$ ` to the first code span of each `Verification:` line that lacks the marker.
This fixes the root cause and prevents a duplicate line.

### Skip group when lines hold a verification line
In `_verification`, check whether the group lines hold a `Verification:` line.
Skip the group when any line matches `_VERIFICATION_LINE`, not only when `group.verification_commands` is non-empty.
This prevents a duplicate line after the marking pass.

### Mark only the first code span on a verification line
The verification template puts the command in the first code span.
Marking only the first code span avoids modifying argument paths or examples.

### Preserve surrounding text
Edit only the command code span and keep surrounding prose and indentation.

## Rejected alternatives

### Skip groups that have any verification line without marking
Rejected: it leaves the command unmarked, so plan check continues to fail.

### Keep appending a generated line
Rejected: it creates two verification lines and leaves later tasks unmarked.

### Mark every code span on a verification line
Rejected: it can mark a path or an example that is not the command.

### Regenerate the full verification line
Rejected: it loses original wording and can change text written by a person.
