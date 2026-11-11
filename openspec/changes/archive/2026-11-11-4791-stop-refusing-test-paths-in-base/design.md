# Design

## Decisions

- **The gate reads test paths only from the specs of the plan.**: The plan writes the specs, so a repair reply can correct a wrong path. The plan does not write the base text of a changed file, so a problem from that text can never pass.
- **A missing test path in a base docstring is not shown as context.**: Most of these paths are example inputs of a test or old locations that do not affect the plan. A context line would add words to each stage request and give the model no task.

## Rejected alternatives

- **Keep the docstring scan and show the source of the path in the message.**: The plan still cannot change the base text at stage time, so the refusal stays. #4498 and #4591 added a same-name hint, and #4401 failed again with the hint at 16:22Z on 2026-11-11.
- **Accept a docstring path when a task of the plan names it.**: The scan finds example inputs such as `tests/test_x.py` and `tests/helper.py` in test docstrings. A plan would have to add a task for text that is correct, which costs a repair reply for no gain.
- **Correct the 43 stale docstring paths in the same change.**: Most are example inputs and not errors, and the change would touch 33 files. With the gate fixed, these paths do not affect a plan.
