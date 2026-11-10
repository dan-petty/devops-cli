# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: the rules in code, the judge with a scripted client, the plan file, the decline, the dry run, the gateway failure and the injection case
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate.py tests/roadmap/test_roadmap_consolidate_judge.py tests/commands/test_roadmap_consolidate_cmd.py`
- [x] 1.2 Add the plan models, the rules, the run and the decline in `src/devops_cli/roadmap/consolidate.py`, the job record key in `store.py`, and the step name `judge` in `failure.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate.py tests/roadmap/test_roadmap_failure.py tests/roadmap/stores`
- [x] 1.3 Add the judge seam, the reply schemas, `GatewayShortlistJudge` and the two prompts
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_consolidate_judge.py`
- [x] 1.4 Add the command, its help and messages, and the dry-run requests
  - Verification: `$ uv run devops ci test tests/commands/test_roadmap_consolidate_cmd.py tests/roadmap/test_roadmap_command_help.py tests/roadmap/test_roadmap_dry_runs.py`

## 2. Documents

- [x] 2.1 Write `docs/roadmap/consolidate.md`, link it from `docs/ROADMAP_WORKFLOW.md`, and regenerate the command documents with `devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up
- Apply of the plan is #3743. The MCP mirror and the weekly row are #3745.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
