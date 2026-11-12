# Proposal: #4950

## Why

The stage job keeps the plan of an item that passed the gates as a file (#4064, #4167). On a hit, `_Planner._gated` takes the kept plan as the first reply and gates it again on the current staged commit. When the commit moved, the `path:LINE:text` citations of the kept plan can point at moved lines, and newer gates can refuse it. That refusal goes through `_returned` and uses one of the `roadmap.stage.gate_returns` returns, so an item with a kept plan gets one planner run less than an item without one. No model request made the kept plan, so its refusal must use no return. Closes #4950.

## What Changes

- In `_Planner._gated`, the job gates the kept plan first. When the checks refuse it, the job logs the refused reply, keeps it in the list of refused replies, and asks the planner for a new first reply with the kept plan and its problem. That reply then has all the returns of `roadmap.stage.gate_returns`.
- The `stage gate returns:` line counts only the returns after the new first reply. A new first reply that passes is no return, so it logs no line.
- After the Service stops, the new first reply does not start, as a return does not (#4900).
- `_Refused.returned` builds the request that sends a refused reply back with its problem, for `_gated` and `_returned`.
- `docs/roadmap/stage.md` states that a refused kept plan uses no return.

## Capabilities

- `roadmap-stage/plan-cache`: a kept plan that the checks refuse uses no gate return, and no new first reply starts after the Service stops.

## Impact

- An item with a refused kept plan gets 1 + `roadmap.stage.gate_returns` planner runs (4 at the default), as an item without a kept plan does. The hard ceiling of 13 planner calls of an item with a review does not change, because the kept plan makes no call.
- No setting, constant, metric or log format changes. The `stage reply refused` line of the kept plan stays (`request=1 input_tokens=0`).
- #4851 depends on this rule.

## Feasibility

- `src/devops_cli/roadmap/stage/stage.py` on `main` at f55a20b99: `_gated` does `proposal = first or self._ask_plan(...)` and passes the kept plan to `_returned`, whose loop adds 1 to `returns` for each refusal, the kept plan included.
- Loki, namespace `devops`, 2026-11-12 05:25Z to 05:55Z, version 0.116.1: item #1858 logged `stage reply refused: item=#1858 request=1 input_tokens=0 tools_offered=False tool_calls=0 limit=none finish_reason=none answered=none result=refused` at 05:29:44Z (the kept plan, no model request), then three refused planner replies, and `stage gate returns: repo=dan-petty/devops-cli item=#1858 returns=3 result=refused` at 05:52:37Z. So the planner got 3 runs, not 4.
- The new test `test_a_kept_plan_that_the_gates_refuse_uses_no_gate_return` fails on `main` with `assert ((), 1, 3) == ((), 1, 4)`, and `test_the_new_first_reply_after_a_refused_kept_plan_gets_the_plan_and_its_problem` fails on `main` with a `returns=1 result=passed` line.
- `log_gate_returns` in `src/devops_cli/roadmap/round_log.py` logs nothing for 0 returns, so a new first reply that passes logs no line.

## Existing Tool Considered

None applies: the rule is the control flow of the stage planner. No new library. Cost to build: about 300,000 tokens and 2 hours.
