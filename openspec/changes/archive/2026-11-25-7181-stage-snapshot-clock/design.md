# Design

## Decisions

- Wrap `run_stage_agent(folders, model=script.model())` inside `with time_machine.travel(NOW, tick=False):` inside `test_agent_phase_offers_stock_tools_only_without_read_issue_or_find_issues` so `datetime.now(UTC)` matches the `now=NOW` argument already passed to `_prepare(...)`, while leaving `fake_github` fixture setup (`time.time() + 600.0`) outside the travel block.

## Rejected alternatives

- Passing a synthetic `now=` parameter into `run_stage_agent`: adds test-only parameters to production code; `AGENTS.md` Rule 2 and existing stage tests favor `time_machine.travel`.
- Bumping `NOW` to a future year: only delays the failure until that date arrives.
