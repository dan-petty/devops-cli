# Design

## Decisions

- Read the plain form again only when the added part is one code span. A span with other words, as the request `open_plan` or `_criteria_section` and pass the criteria, says something other than a parameter, and #4490 removed those reads on purpose.
- `ast` decides the parameter shape: the span is a parameter list when `def _(<span>): pass` parses as one function. A decorator and an option do not parse. A constant in capitals parses, so a parameter whose name is all capitals is no parameter.
- Accept `the` before the span. The archived task Add the `verifier` to `plan_stage` adds a parameter, and no other archived task or stored reply reads a new name with it.
- `changed_functions` stays syntactic. A class, an enum or a model can come out of it, as `StageProposal` does for add `constant_claims` to `StageProposal`, and the `def` filter of `calling_files` drops it. The test of the field of a model checks the gate, not the read.

## Rejected alternatives

- Go back to the rule before #4490 (any text between Add and to). It brings back the false refusals of a member, a property, a decorator and a name in the next clause.
- Drop a name in CapWords in `changed_functions`. The `def` filter of `calling_files` already reads what the name is, with `ast`, and a naming convention is a guess.
