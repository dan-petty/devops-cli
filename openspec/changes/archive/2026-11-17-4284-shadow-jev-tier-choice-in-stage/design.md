# Design

## Decisions

- **Add a boolean `roadmap.stage.jev_shadow`, default off, beside `roadmap.stage.jev_completeness`.**: Shadow mode must cost nothing until a person turns it on, and the setting follows the pattern of the completeness switch.
- **Run the call in `_Planner.plan`, before the first plan call, and only when the item has no kept plan.**: The record belongs to the first plan of an item. A kept plan uses no plan call, so it needs no shadow call either.
- **Use one helper that catches every exception, logs the error, counts `choice=error` and returns.**: A Jev error must never stop the item. The helper follows the catch-all pattern of `src/devops_cli/roadmap/intake/intake_jev_shadow.py:197`.
- **Add an optional `extra_questions` parameter to `route_with_jev`, and `extra_probabilities` to `JevRouteDecision`.**: One request then carries the tier choice and the concrete-files question, so the cost stays one call. Existing callers stay valid.
- **Use the tier key of `picked_model` as the label, with two tiers `deepseek` and `sonnet`.**: The counter has exactly the values `deepseek`, `sonnet` and `error`, so the label is the picked tier with no mapping.
- **Add a `jev_route` parameter to `_Planner` as the test seam.**: The test injects a fake Jev and the module makes no network call, which follows the seam style of the stage tests and adds no `unittest.mock.patch`.

## Rejected alternatives

- **Default the switch on.**: It spends tokens and adds a hosted call without consent.
- **Make a second Jev call for the concrete-files question.**: It doubles the calls and the cost.
- **Use `selected_model` after escalation as the label.**: It hides the raw choice that Jev made.
- **Let a Jev error pass to the stage job.**: It would change stage behaviour, which shadow mode forbids.
- **A new routing function in the stage module.**: It duplicates the tested code of `route_with_jev`.
