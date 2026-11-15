# Design

## Decisions

- **Bound the earlier plan only when the full return request passes the limit.**: The issue asks for the bound under that condition, and a request that fits keeps the full earlier plan for the planner to revise.
- **Measure the request as the planner sends it, the JSON text of the prompt, at the same target as the first request: `tool_stop(window)` less `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS`.**: The bound and the test then use one measure, and the reserve covers the prompts and the message JSON that the run hook counts beside the request.
- **Cut only the texts of the earlier plan, and keep every key, every path, the summary and the problem.**: The planner revises the plan by its keys and its paths, so a cut that removed them would give it nothing to revise.
- **Give each text a share of the room that its length gives it, and halve the share while the measured request still passes the target.**: A plan with one long text and many short ones keeps its short texts, and the loop settles below the target although the JSON of the keys adds tokens that no text holds.
- **Put the measure and the bound in a new module `src/devops_cli/roadmap/stage/stage_return.py`, called by `_Refused.returned` and by `_repaired`.**: Both return paths then build the request one way, and the typed request module of `src/devops_cli/roadmap/stage/stage_request.py` keeps its one job.
- **Reuse the staged `CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS` of 8,192 tokens and add no constant, so the entry of `tests/roadmap/test_roadmap_limit_classes.py` stays as it is.**: The change adds no limit of its own: it bounds the earlier plan against the limit that the first request already uses, so the registry test needs no new entry, and group 1 names the declared path in its task text.
- **Add the measure tests to `tests/roadmap/stage/test_roadmap_stage_window.py`.**: That module holds the measure of the first request, its `_limit` helper and its scripted model with a real checkout, so the return measure sits beside the measure it extends.

## Rejected alternatives

- **Always cut the earlier plan to a fixed token budget.**: The limit follows the window: `src/devops_cli/roadmap/refine/refine_investigation.py:404:return window - window // CONST_ROADMAP_INVESTIGATION_REPLY_WINDOW_SHARE`, so a fixed budget cuts a plan that fits a large window.
- **Drop the earlier plan when the request passes the limit.**: The return exists so the planner revises its own reply: `src/devops_cli/roadmap/stage/stage.py:1162:return {**request.for_model(), "previous": self.reply.model_dump(), "problem": self.problem}`.
- **Send the earlier plan as one truncated JSON string.**: The planner and the gates read the plan by its keys: `src/devops_cli/roadmap/stage/stage.py:1896:"previous": change.proposal.model_dump(),` sends it as an object with its keys.
- **Raise the planner window instead of bounding the request.**: The first request keeps `src/devops_cli/config/constants.py:3429:CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS: Final[int] = 8_192` below the limit at every window, and the return request is unbounded at every window.
- **Reuse pydantic-ai's `ProcessHistory` capability for the bound.**: It trims the message history before a request and cannot cut the `previous` field of one request: the request is one JSON document that `_ask_plan` writes in one piece.
- **Add a new constant for the room that the bound leaves the earlier plan, with its entry in `tests/roadmap/test_roadmap_limit_classes.py`.**: The room follows the window and the reserve of the first request, so a second constant would restate `src/devops_cli/config/constants.py:3429:CONST_ROADMAP_STAGE_TOOL_RESERVE_TOKENS: Final[int] = 8_192` and could drift from it.
