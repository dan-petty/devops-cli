# Design

## Decisions

- **The reader of the staged constants lives in a new module `src/devops_cli/roadmap/stage_constants.py`.**: `stage_change.py` is already long, and the reader adds git calls and ast parsing beside the reply schema.
- **`check_proposal` takes a keyword-only `constants: Mapping[str, int] | None`, and its caller passes the values that `staged_constants` read for the claimed names.**: The caller holds the checkout and the commit, and the replay passes none and reads no git.
- **`constant_claims` is optional with an empty default and stays out of `_PLAN_KEYS`.**: A reply that gives no list still validates, and the prose scan judges it.
- **`staged_constants` returns only module-level integer literals of `src/`, read by the claimed name.**: `ast.literal_eval` gives the value with no code run, and one git grep and git show for each claim bounds the cost.
- **The prose scan runs only when `constant_claims` is empty.**: A plan that gives its claims is judged by the claims, and the prose parse stays brittle.

## Rejected alternatives

- **Put the reader in `stage_change.py`.**: The module of the reply schema and the renderer already holds the checks, the schema and the measure; the context shows no git call in it.
- **Let `check_proposal` read git itself.**: The replay calls `check_proposal` through `stage_eval_gates` and reads no git, so the replay would fail.
- **Make `constant_claims` a required key in `_PLAN_KEYS`.**: The context shows `_PLAN_KEYS` holds the keys that a reply must set, so a required key refuses every reply that an older prompt produced.
- **Read every assignment of `src/`, computed values included.**: A computed value needs code run, and the reader must run no code of the staged tree.
