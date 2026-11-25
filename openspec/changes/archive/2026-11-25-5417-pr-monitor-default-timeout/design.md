# Design

## Decisions

- **Single shared default constant `DEFAULT_PR_MONITOR_TIMEOUT_SECONDS = 600`**: Putting the default in `src/devops_cli/config/defaults.py` and referencing it in `monitor_pr_command`, `monitor_pr`, and `plan_pr_monitor` guarantees the CLI option, runtime poller, dry-run plan, and FastMCP schema stay identical.
- **600-second bound**: Covers observed 6–7 minute code-PR check settle times with margin while remaining finite so hung checks still time out cleanly.

## Rejected alternatives

- **Keep 300 seconds**: Times out before shards plus aggregate `Tests & Coverage` settle.
- **Hardcode 600 inline in each function**: Risks drift between the Typer option default, `monitor_pr`, and `plan_pr_monitor`.
