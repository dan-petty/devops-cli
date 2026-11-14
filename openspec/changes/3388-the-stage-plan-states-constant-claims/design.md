# Design

## Decisions

- **`constant_claims` is a field of `StageProposal` with an empty default, and a reply that gives no list is judged by the prose scan.**: A reply with no structured claim has no value to compare, and the prose scan is the only reading of it.
- **`check_proposal` takes the staged values as a keyword-only mapping.**: The stage job holds the checkout and the commit, and the replay passes recorded values and reads no git.
- **A claim whose name the mapping lacks is refused, with its own message.**: A structured claim gives one name and one value, and a new name for an existing bound is the defect that this item removes.
- **The prose scan runs only when `constant_claims` is empty.**: A plan that gives claims is judged by the claims, and a sentence with two numbers stays ambiguous.
- **The claim examples and the tests use `SUMMARY_MAX_CHARS`, whose staged value is 60.**: `BODY_MAX_CHARS` has two staged definitions with different values, so it has no one staged value to compare.
- **`claimed_names` lives in `src/devops_cli/roadmap/stage/stage_constants.py`, and the stage job calls it.**: A claim whose name appears in no plan text must still be read, or the check never sees it.

## Rejected alternatives

- **Parse the claims from the prose with a second reader.**: `constant_problems` skips a sentence with two numbers and a name the tree does not define, which is the defect that this item removes.
- **Read the staged values inside `check_proposal`.**: The replay passes recorded values with `src/devops_cli/roadmap/stage/stage_eval_gates.py:145:constants=dict(case.facts.constants),` and reads no git.
- **Make `constant_claims` a required key of the reply.**: The recorded cases of the stage eval and the replies of an older prompt hold no such key, so a required key refuses them.
- **Use `BODY_MAX_CHARS` as the claim example.**: `src/devops_cli/roadmap/stage/stage_change.py:125:BODY_MAX_CHARS: Final[int] = 800` and `src/devops_cli/roadmap/pull_form.py:55:BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` give two staged values, so the reader resolves no one value.
