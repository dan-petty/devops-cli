# Tasks

## 1. Render the recorded trace of the last run from one item read

Kind: behavior. Reads: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/security/sanitizer.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/follow.py` (new), `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_follow.py` (new).

- [ ] 1.1 Add `tests/roadmap/test_roadmap_follow.py::test_the_table_holds_one_row_for_each_step_of_the_trace` first: an item whose record holds `implement.trace` with model, check and attempt events for two steps gives a state whose table holds the header and two rows, the failing step with its command, and an item whose record holds no `implement.trace` and no `implement.job` gives the never-run line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_follow.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/roadmap/follow.py` with `FollowState` (the trace, the runner Job name and the Job state), `follow_state(item, number)` that reads `item.job_record` for `ImplementRecordKey.TRACE`, `ImplementRecordKey.JOB` and `ImplementRecordKey.JOB_STATE` and decodes the trace with `decode`, `recorded_rows(trace)` that builds one `SummaryRow` for each step from its attempt, model and check events, `render_recorded(state)` that masks each text with `mask_secrets` and renders `summary_table` or the never-run line, and `follow_command(number)`. Add the never-run line, the follow command text, the inbox follow text and the explain follow text to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_follow.py` passes

## 2. Read and mask the tail of the runner Job pod log

Kind: behavior. Reads: `src/devops_cli/k8s/cluster_job_api.py`, `src/devops_cli/security/sanitizer.py`. Changes: `src/devops_cli/roadmap/follow_live.py` (new), `tests/roadmap/test_roadmap_follow_live.py` (new).

- [ ] 2.1 Add `tests/roadmap/test_roadmap_follow_live.py::test_a_secret_in_the_pod_log_is_masked` first: a fake cluster client whose log holds a line with a token of the masking rules gives the masked line and not the token
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_follow_live.py` fails on the base
- [ ] 2.2 Add `src/devops_cli/roadmap/follow_live.py` with `live_lines(jobs, name, lines)`: it reads the log of the Job `name` through `log_tail`, masks each line with `mask_secrets`, and returns the lines. It reads no GitHub data and parses no line
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_follow_live.py` passes

## 3. Add the follow command with one issue read

Kind: behavior. Reads: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/request_plan.py`, `src/devops_cli/roadmap/follow.py`, `src/devops_cli/roadmap/follow_live.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/roadmap/test_roadmap_explain_command.py`. Changes: `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `tests/roadmap/test_roadmap_follow_command.py` (new), `tests/commands/test_all_commands_help_dryrun.py`.

- [ ] 3.1 Add `tests/roadmap/test_roadmap_follow_command.py::test_follow_reads_the_item_once_and_prints_the_live_line` first: with the store patched to the in-memory fake, an item whose record holds a trace and a running Job name, and a fake cluster client, the command prints the table and the masked live line, `store.reads` is `["item"]`, and a finished Job makes no cluster request
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_follow_command.py tests/commands/test_all_commands_help_dryrun.py` fails on the base
- [ ] 3.2 Add `follow_cmd` to `src/devops_cli/commands/roadmap.py` under `@app.command("follow", help=HELP.roadmap.follow)` and `@dry_run_class("request-plan")`, with the issue argument, `--repo`, `--lines` (default `DEFAULT_LOG_TAIL_LINES`) and `--dry-run`. It opens the store, calls `store.item(item)` once, prints `render_recorded(follow_state(held, item))`, and, while the state names a Job with no recorded state, prints the masked lines of `live_lines`. Its dry run prints the one read from `explain_requests(target, item=item, trace=True)`. Add `HELP.roadmap.follow` and the help of its options to `src/devops_cli/lang/en/help.py`, and the row `(roadmap_app, ["follow", "--help"])` to `COMMAND_SPECS` in `tests/commands/test_all_commands_help_dryrun.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_follow_command.py tests/commands/test_all_commands_help_dryrun.py` passes

## 4. Print the follow command from each inbox line that names an item

Kind: behavior. Reads: `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/follow.py`, `src/devops_cli/roadmap/inbox_kind.py`. Changes: `src/devops_cli/roadmap/inbox.py`, `tests/roadmap/test_roadmap_inbox.py`.

- [ ] 4.1 Add `tests/roadmap/test_roadmap_inbox.py::test_only_a_line_that_names_an_item_holds_the_follow_command` first: the line of a blocked item holds the follow command with that item's number, and the line of the plan pull request of the same item holds no follow command
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` fails on the base
- [ ] 4.2 Add the field `item: int | None = None` to `InboxLine` in `src/devops_cli/roadmap/inbox.py`, and set it from `item.number` in `_blocked_line`, `_refine_lines`, `_split_lines`, `_alternatives_lines`, `_failed_lines` and `_claim_lines`; leave it None in `_pull_line`, `_draft_line`, `_label_lines` and `_queue_lines`, so no line whose number is a pull request's carries it. `_render_line` adds the text of `MESSAGES.roadmap.inbox_follow` with `follow_command(line.item)` only when `line.item` is not None. Pass `item=7` in `test_the_report_names_the_refine_section` of `tests/roadmap/test_roadmap_inbox.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_inbox.py` passes

## 5. Print the follow command from explain

Kind: behavior. Reads: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/follow.py`. Changes: `src/devops_cli/roadmap/explain.py`, `tests/roadmap/test_roadmap_explain.py`.

- [ ] 5.1 Add `tests/roadmap/test_roadmap_explain.py::test_the_output_names_the_follow_command` first: the explanation of an item holds the follow command followed by its number
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py` fails on the base
- [ ] 5.2 Print the follow command of the item from `render_explanation` in `src/devops_cli/roadmap/explain.py`, with `explained.number` and `follow_command`, and send no request for it
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_explain.py` passes

## 6. Document the command and its access

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/lang/en/help.py`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`.

- [ ] 6.1 Name the `follow` command beside the other read-only roadmap commands in `docs/ROADMAP_WORKFLOW.md`, and state its one GitHub request and the kubeconfig permissions get and list on pods and get on pods/log. Regenerate `docs/CLI_REFERENCE.md` with the docs generator
  - Verification: `$ uv run devops ci docs` passes
- [ ] 6.2 Edit `docs/ROADMAP_WORKFLOW.md` to name the command, its one GitHub request and the three kubeconfig permissions, then regenerate `docs/CLI_REFERENCE.md` with the docs generator
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 3: `follow` works for a running Job and for a finished one.
- Group 3: It reads at most a stated number of GitHub requests and none for the live part (it reads the pod).
- Group 1: The output is in the same shape as the PR comment table.
- Group 2: It masks secrets like the log lines do.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
