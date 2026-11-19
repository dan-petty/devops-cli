# Proposal: #6355

## Why
The stage job passed 68 of 140 attempts in the 7 days to 2026-11-19 (49%). Since the raise of 2026-11-16, 5 of its 6 gate refusals ended at return 6, and by the owner rule a limit of a job under 80% goes up. Its queue grew from 186 to 207 items in one day, and the next stage Job started a median of 9.1 minutes after a Job ended. The fix-checks task has the code window of 128,000 tokens, although it runs a step of the implement job, which has 256,000. Six comments of the template state old facts. Closes #6355.

## What Changes
- `roadmap.stage.gate_returns` goes from 6 to 8. `gate_return_extensions` stays 2.
- `roadmap.stage.backlog_interval_minutes` 4 and `backlog_threshold` 10: while the stage queue holds 10 or more items, the next round starts at the next poll.
- `ai.tasks.fix_checks` names the DeepSeek group with a 256,000-token window.
- Comments: the local-model rule, the reason for the 256,000-token window of stage and implement, what `roadmap.stage.limit` controls, what `roadmap.mcp` controls, and three notes about old images.
- These are values of a manifest that the Service reads, so the change carries a spec delta. It adds no test of a value (owner rule of 2026-11-16); a command proves it.

## Capabilities
- `roadmap-service-deployment`: one ADDED requirement.

## Impact
- All three value changes loosen a limit or add a setting, so the live ConfigMap needs no step before a release. `roadmap.*` reloads each round, and each fix-checks Job reads `ai.tasks` at start. No Service restart.
- A stage attempt can make 2 more plan runs, about 1.9 million tokens each. The backlog rule adds about 6 counted GitHub requests per extra round, under 2% of the budget of 4,000 an hour.

## Feasibility
- `Settings.model_validate` loads the changed template data, and the ConfigMap that `render_active_devops_configmap` gives from it. The render differs from the live ConfigMap of 2026-11-19 in exactly these five keys: `ai.tasks.fix_checks.model`, `ai.tasks.fix_checks.context_window`, `roadmap.stage.backlog_interval_minutes`, `roadmap.stage.backlog_threshold` and `roadmap.stage.gate_returns`.
- The settings refuse `gate_returns` above 12 (spec `roadmap-stage/returns`), and `backlog_interval_minutes` above `interval_minutes`.
- The figures come from the job result lines in Loki, the grades of `devops roadmap eval grades --window 7d`, the series `devops_cli_roadmap_tool_limit_hits_total` and the OpenRouter endpoints API, read on 2026-11-19.

## Existing Tool Considered
No tool applies: the change sets values of existing settings in the ConfigMap template. It builds nothing.
