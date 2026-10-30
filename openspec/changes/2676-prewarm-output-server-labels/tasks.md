# Tasks

## 1. Name each server by host and port

- [ ] 1.1 Write the tests in `tests/test_ai_prewarm.py` that call the MCP tool, `devops ai prewarm --json` and `devops ai preload` with a URL that holds a user name and a query value, and that check the model label of the counter, and verify that `uv run devops ci fail-to-pass --base origin/main` fails on the base
- [ ] 1.2 Add the helper `bounded_label` in `src/devops_cli/telemetry/instruments.py`. In `src/devops_cli/commands/ai.py`, map the result keys with `server_label` for `prewarm` and `preload`, and give the counter the bounded label, and verify that `uv run devops ci test tests/test_ai_prewarm.py tests/test_ai_cmd.py` passes
- [ ] 1.3 Run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
