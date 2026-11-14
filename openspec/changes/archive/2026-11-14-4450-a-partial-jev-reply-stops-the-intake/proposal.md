# Proposal: #4450 fix(roadmap): a partial Jev reply stops the intake round

## Why
A partial or wrong-kind Jev reply does not stop the intake round. The decision model raises `UnexpectedModelBehavior` before intake reads the reply, and `FAILED` holds that error, so both modes fail open. The shadow module still holds a guard that checks nothing: `_answer_of(response, f"duplicate_of_{each.number}", object)` cannot fail, because `isinstance(None, object)` is true. Its docstring also says that a missing answer raises `ShadowError`, but only the choice and score answers are checked. Closes #4450.

## What Changes
- Remove the no-op loop and dead guard `_answer_of(..., object)` from `_duplicate` in `src/devops_cli/roadmap/intake/intake_jev_shadow.py`.
- Remove the repeated `duplicate_of_` string literal from `intake_jev_shadow.py`.
- Update the docstring of `observation_of` to correctly state that `ShadowError` is raised for a missing or wrong-kind choice or score answer, and that the decision model refuses a partial reply.
- Add tests to verify that `_duplicate` holds no `duplicate_of_` literal or `_answer_of` call of kind `object`, that `observation_of` raises `ShadowError` on missing priority answer, and that the docstring matches the behavior.

## Capabilities
- `roadmap-intake-jev`: shadow duplicate check and answer error verification.

## Impact
- Eliminates dead guard code and misleading docstrings in `intake_jev_shadow.py`.
- No breaking API changes; internal implementation cleanup only.

## Feasibility
- Verified in `src/devops_cli/roadmap/intake/intake_jev_shadow.py`: `isinstance(None, object)` evaluates to True, making the guard a no-op.
- Verified that `SystemOneModel.decide` enforces complete answers and matching kinds, raising `UnexpectedModelBehavior` before intake processes the response.

## Existing Tool Considered
`pydantic-ai` covers the need: `SystemOneModel.decide` raises `UnexpectedModelBehavior` when answer names or kinds differ from questions. The project builds no new code beyond removing the 3-line dead guard and updating docstrings.
