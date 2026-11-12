# Design

## Decisions

- **Read a removal from two clause forms.** A requirement removes a name when the name is the subject of MUST NOT or SHALL NOT with the verb exist or be available, or the object of MUST NOT or SHALL NOT with the verb register, offer, list, accept, expose or provide. The plans and specs of the repository use these two forms for a removal: the tests of #3287 write "The `devops roadmap intake-eval` command MUST NOT exist.", and the plan of #3185 wrote "MUST NOT register `devops roadmap intake-eval` as a command or as an alias".
- **A subject starts a clause.** The subject form matches only at the start of a line, after a punctuation mark and a space, or after `and` or `or`. So in "The command `devops a` SHALL stay, and `devops b` MUST NOT exist." only `devops b` is removed.
- **The head of "X of Y" is X.** "The `--old` option of `devops x` MUST NOT exist." removes `--old` and keeps `devops x`.
- **Only the names in the governed phrase count.** The check takes the code spans of the matched subject or object, and keeps the filter on `devops ` and `--`.

## Rejected alternatives

- **The subject form only, as the diagnosis proposed.** It loses the object form of #3185, "MUST NOT register `devops roadmap intake-eval` as a command", which is the real defect that #3287 was filed for.
- **The code span nearest to MUST NOT.** In the #2530 sentence the nearest span before MUST NOT is `devops pr check-readiness`, so the false refusal stays.
- **spaCy dependency parsing.** It adds a package and a separately downloaded model to the Service image for one check, and the two clause forms above cover each removal in the repository.
