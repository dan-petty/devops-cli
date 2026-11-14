# Design

## Decisions
- **Remove dead guard instead of adding checked accessor**: The decision model (`SystemOneModel.decide`) already refuses a partial reply before intake reads it, and `FAILED` holds `UnexpectedModelBehavior`, so both modes fail open. Adding a checked accessor would serve an unreachable path (AGENTS.md rule 2). Removing the dead guard removes dead code.
- **Reference duplicate prefix only in `intake_jev.py`**: Do not repeat the `"duplicate_of_"` literal in `intake_jev_shadow.py`. `best_neighbour` already accesses the prefix defined in `intake_jev.py`.
- **Docstring accuracy**: Clarify in `observation_of` docstring that `ShadowError` applies to missing or wrong-kind choice and score answers, and that the underlying decision model refuses partial replies.

## Rejected alternatives
- **Add checked accessor**: Rejected because `SystemOneModel` already raises `UnexpectedModelBehavior` for partial replies, so intake never receives them.
- **Close as not planned**: Rejected because the dead guard and incorrect docstring would remain in the codebase.
