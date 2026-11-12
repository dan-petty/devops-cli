# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests with recorded runner event files: a changed template with a diff, a changed template with the diff hidden, a skipped `command`, a notified restart handler, a reboot task, a failed task, the same plan id for the same events, another id for another commit or limit, no host of `offline` in the limit, the refusal of an agent at `none` before any process, and a dry run with no process
  - Verification: `$ uv run devops ci test tests/infra/test_plan.py tests/commands/test_infra_plan.py`
- [x] 1.2 Add `infra/plan.py`, `export_commit` and the ref steps in `infra/repo_tree.py`, the plan models, the dry-run plan and the command `devops infra plan`
  - Verification: `$ uv run devops ci test tests/infra tests/commands/test_infra_plan.py tests/commands/test_infra_status.py tests/commands/test_infra_onboard.py`
- [x] 1.3 Run the command live on dan-petty/homelab on hawk, and compare `uptime -s` and the `k3s-agent` start time of hawk before and after
  - Verification: `$ uv run devops infra plan dan-petty/homelab ansible/playbooks/03_k3s.yaml --limit hawk.lan`

## 2. Documents

- [x] 2.1 Add the glossary terms to CONTEXT.md and regenerate the command reference
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
