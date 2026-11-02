# Tasks

## 1. Build the follow rows from the pod log and the job record

Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/implement.py`, `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/roadmap/follow.py` (new), `tests/roadmap/test_roadmap_follow.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_follow.py` first: a fake pod log with a step line, a tool call, a check result and an attempt, and a fake issue body with a job record, each produce rows; a log line with a secret produces a masked row; and the count of GitHub reads stays at one, and verify that `uv run devops ci test tests/roadmap/test_roadmap_follow.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/follow.py`. `read_live_rows` reads the pod log of the runner Job through the Kubernetes client and parses the step, tool call, check and attempt lines. `read_history_rows` parses the job record of the issue body. `read_follow` builds both row lists, masks each value with the masker of the log lines, and sends at most one GitHub request for the issue body, and verify that `uv run devops ci test tests/roadmap/test_roadmap_follow.py` passes

## 2. Add the follow command and its table

Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/follow.py`, `src/devops_cli/lang/en/help.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/follow.py`, `tests/roadmap/test_roadmap_follow_command.py` (new).

- [ ] 2.1 Write `tests/roadmap/test_roadmap_follow_command.py` first: the command prints the header of the PR comment table in its column order, and a `--dry-run` lists its reads and sends none, and verify that `uv run devops ci test tests/roadmap/test_roadmap_follow_command.py` fails on the base
- [ ] 2.2 Add the `follow` command to `src/devops_cli/commands/roadmap.py`. It takes the issue number, calls `read_follow`, and prints the rows with the PR comment table renderer. Add the `follow` help text to `src/devops_cli/lang/en/help.py`, which names the live part and the one GitHub request, and verify that `uv run devops ci test tests/roadmap/test_roadmap_follow_command.py` passes

## 3. Link follow from the inbox and explain output

Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/test_roadmap_inbox_command.py`, `tests/roadmap/test_roadmap_explain_command.py`. Changes: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/test_roadmap_inbox_command.py`, `tests/roadmap/test_roadmap_explain_command.py`.

- [ ] 3.1 Extend `tests/roadmap/test_roadmap_inbox_command.py` and `tests/roadmap/test_roadmap_explain_command.py` first: each output holds `devops roadmap follow <number>` for the item that it lists, and verify that `uv run devops ci test tests/roadmap/test_roadmap_inbox_command.py tests/roadmap/test_roadmap_explain_command.py` fails on the base
- [ ] 3.2 Add the follow line to each row that `src/devops_cli/roadmap/inbox.py` and `src/devops_cli/roadmap/explain.py` build. The line names the command and the issue number, and verify that `uv run devops ci test tests/roadmap/test_roadmap_inbox_command.py tests/roadmap/test_roadmap_explain_command.py` passes

## 4. Document the follow command

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/inbox.md`. Changes: `docs/roadmap/follow.md` (new), `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`.

- [ ] 4.1 Add `docs/roadmap/follow.md`: what the command prints, the live part from the pod log, the one GitHub request for the job record, the table shape and the masking. Name the command in the notes of `docs/ROADMAP_WORKFLOW.md` beside `explain` and `inbox`, and add its row to `docs/CLI_REFERENCE.md`, and verify that `uv run devops ci docs` passes
- [ ] 4.2 docs/roadmap/follow.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Criteria

- `follow` works for a running Job and for a finished one.: group 1
- It reads at most a stated number of GitHub requests and none for the live part (it reads the pod).: group 1
- The output is in the same shape as the PR comment table.: group 2
- It masks secrets like the log lines do.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
