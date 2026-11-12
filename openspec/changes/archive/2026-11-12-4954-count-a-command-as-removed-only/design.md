# Design

## Decisions

- **Read a removal from two clause forms.** A requirement removes a name when the name is in the subject of MUST NOT or SHALL NOT with the verb exist, be available or the passive of a verb that offers a name, or in the object of MUST NOT or SHALL NOT with the verb register, offer, list, accept, expose, provide, support, have or keep. A list of these verbs can share one object ("MUST NOT register or list `x`"), and a colon after the verb starts a list of subjects ("The following commands MUST NOT exist: `a` and `b`."). The plans and specs of the repository use these two forms for a removal: the tests of #3287 write "The `devops roadmap intake-eval` command MUST NOT exist.", and the plan of #3185 wrote "MUST NOT register `devops roadmap intake-eval` as a command or as an alias".
- **The subject is the text from the start of its clause.** The clause starts at the start of the line, after a sentence mark, or after a parenthesis that does not close before the verb. So an article, an adjective, a trailing noun, bold marks and a closed parenthesis can be in the subject, and no closed list of words decides it. When a modal verb of an earlier clause is in this text, the subject starts after the first comma, `and`, `or` or `but` after that modal verb. So in "The command `devops a` SHALL stay, and `devops b` MUST NOT exist." only `devops b` is removed.
- **The object is the text to the end of its clause.** It ends at a sentence mark, a closing parenthesis or the end of the line. When a modal verb starts a new clause in it, the object ends at the last comma, `and`, `or` or `but` before that modal verb.
- **A span after a preposition is not the head.** A span is not removed when a preposition or a word that starts a subordinate clause (of, for, between, when, that and the like) is between it and the span or the comma before it. "The `--old` option of `devops x` MUST NOT exist." removes `--old` and keeps `devops x`, and "When `devops x` runs, the `--old` option MUST NOT be available." removes `--old` only.
- **Only the names in the governed phrase count.** The check takes the code spans of the subject or the object, and keeps the filter on `devops ` and `--`.
- **The prompt gives the planner the sentence that the check reads.** The rule for a removed or renamed command tells the planner to write "`<old name>` MUST NOT exist.". A test reads the sentence from the prompt and sends it through `check_proposal`, so the prompt and the check cannot drift apart.

## Rejected alternatives

- **The subject form only, as the diagnosis proposed.** It loses the object form of #3185, "MUST NOT register `devops roadmap intake-eval` as a command", which is the real defect that #3287 was filed for.
- **The code span nearest to MUST NOT.** In the #2530 sentence the nearest span before MUST NOT is `devops pr check-readiness`, so the false refusal stays.
- **A closed list of words before the span ("The" or "Each" and a noun).** The first version of this change used it. A review showed 13 removals that the old rule caught and that it missed, such as "The old `x` command MUST NOT exist." and "`x` MUST NOT be registered as a command.".
- **spaCy dependency parsing.** It adds a package and a separately downloaded model to the Service image for one check, and the two clause forms above cover each removal in the repository.
