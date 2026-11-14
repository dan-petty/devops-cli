# Proposal

## Why

A person learns what a roadmap Job did from `kubectl logs` and from one comment at the end, so a running Job is opaque, and `devops roadmap explain` says why an item is taken, not what the Job does. #3076 asks for one command that shows the trace of the run and the live log of its pod.

## What Changes

- Add `src/devops_cli/roadmap/follow.py`: it takes the trace, the runner Job name and the Job state from one item read, builds one table row for each step of the trace, masks each text with `mask_secrets`, and formats the follow command of an item.
- Add `src/devops_cli/roadmap/follow_live.py`, which reads the tail of the pod log of the runner Job through `log_tail` and masks each line with `mask_secrets`.
- Add the `follow` command to `src/devops_cli/commands/roadmap.py`: one item read gives the trace and the Job, the live tail follows it, the dry run lists the one read, and its class is `request-plan`.
- Add the help of the command to `src/devops_cli/lang/en/help.py` and its row to `tests/commands/test_all_commands_help_dryrun.py`.
- Print the follow command of each item from `src/devops_cli/roadmap/inbox.py` and `src/devops_cli/roadmap/explain.py`, and print none on a line whose number is a pull request's.
- Name the command, its one GitHub request and the three kubeconfig permissions in `docs/ROADMAP_WORKFLOW.md`, and regenerate `docs/CLI_REFERENCE.md`.
- The change carries a spec delta: a new command, its output, its help and its row in the command reference are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-follow`: The console prints the recorded trace as the comment table, One read of the item gives the trace and the runner Job, The console prints the masked tail of a running Job, An item with no recorded run is named as never run, Every text of the console is masked, The command reference states the budget and the access

### Modified Capabilities

- `roadmap-inbox`: The inbox line names the follow command of its item
- `roadmap-explain`: Explain names the follow command of the item

## Impact

- Code: `src/devops_cli/roadmap/follow.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/follow_live.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`
- Tests: `tests/roadmap/test_roadmap_follow.py`, `tests/roadmap/test_roadmap_follow_live.py`, `tests/roadmap/test_roadmap_follow_command.py`, `tests/commands/test_all_commands_help_dryrun.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_explain.py`

## Feasibility

- The plan that a person closed said that the pull request comment table did not exist, and the table exists now: `src/devops_cli/roadmap/implement/implement_trace.py:345:def summary_table(rows: Iterable[SummaryRow]) -> str:` renders it, `src/devops_cli/roadmap/implement/implement_trace.py:315:class SummaryRow:` holds one row, and the living rule is `openspec/specs/roadmap-implement-job/stops/spec.md:168:The table SHALL list at most `CONST_ROADMAP_IMPLEMENT_TABLE_ROWS` rows, the newest`. The console reuses that renderer and parses no log line.
- The record still keeps one trace, at `src/devops_cli/roadmap/stores/store.py:396:TRACE = "implement.trace"`, which a new run replaces, so the console shows the trace of the last run and no history of earlier runs. The plan adds no second store and no code that compensates.
- The probe line "The path `docs/ROADMAP_WORKFLOW.md` is a file of the staging commit." confirms the workflow page that the plan changes, and "The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit." confirms the message module.
- The probe line "The path `security/sanitizer.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/security/sanitizer.py`. No commit in the history deleted or renamed it." fixes the masker path, and `src/devops_cli/security/sanitizer.py:454:def mask_secrets(text: str, syntax: Literal["code", "data"] | str = "data") -> str:` is the function that the plan reuses.
- The probe line "The path `implement.job` is no file of the staging commit. No commit in the history deleted or renamed it." is no false premise: `implement.job` is a key of the job record, held with the trace and the Job state at `src/devops_cli/roadmap/stores/store.py:396:TRACE = "implement.trace"`, `src/devops_cli/roadmap/stores/store.py:397:JOB = "implement.job"` and `src/devops_cli/roadmap/stores/store.py:398:JOB_STATE = "implement.job_state"`.
- The probe line "Not probed, the bound of 10 commands is reached: `src/devops_cli/commands/roadmap.py`, `It.read`, `inbox`, `explain`, `follow`, `get`, `list`, `mask_secrets`" shows that no probe read the new command: it does not exist at this commit, and this change creates it.
- The probe line "Commit dfb09bd1 2026-11-12 refactor(openspec): split big capabilities into nested ones (#4981) deleted or renamed it." shows that the old capability path was split, so the plan cites the nested living spec `openspec/specs/roadmap-implement-job/stops/spec.md` and not the old path.
- The review finding on group 4 is a real defect, and the plan fixes it: `src/devops_cli/roadmap/inbox.py:68:"""One thing that waits for a person: what it is, the number of its issue or pull request` states that the number is an issue's or a pull request's, `src/devops_cli/roadmap/inbox.py:155:return InboxLine(kind, pull.number,` gives a pull request's number to the plan, implement, release, draft and person lines, and `src/devops_cli/roadmap/inbox.py:198:return InboxLine(InboxKind.BLOCKED, item.number,` gives an item's number to a blocked line. The group now marks each item line with a new `item` field and prints the follow command from that field only, so no line prints a follow command for a pull request number.
- A `search_code` for `def item(self, number` found `src/devops_cli/roadmap/stores/store.py:1018:def item(self, number: int) -> Item | None:`, whose one issue read holds `Item.job_record` with the trace, `implement.job` and `implement.job_state`, so one read gives all three.
- A `search_code` for `def log_tail` found `src/devops_cli/k8s/cluster_job_api.py:255:def log_tail(self, name: str, lines: int) -> str:`, which lists the pods of a Job by its label and returns the log of its pod, and that is the live read of the plan.
- A `search_code` for `def explain_requests` found `src/devops_cli/roadmap/request_plan.py:1121:def explain_requests(` and its branch `src/devops_cli/roadmap/request_plan.py:1130:if trace:`, which returns one issue read and no write, so the dry run lists the one request of the command.
- A `read_file` of `src/devops_cli/roadmap/implement/implement_trace.py` lines 55-240 showed that each event holds its step and each attempt its outcome at `src/devops_cli/roadmap/implement/implement_trace.py:217:def attempt(`, so the rows come from the events and no parser reads the log.
- The bounds that the plan relies on are `src/devops_cli/config/constants.py:3605:CONST_ROADMAP_IMPLEMENT_TABLE_ROWS: Final[int] = 30` for the table and `src/devops_cli/config/defaults.py:762:DEFAULT_LOG_TAIL_LINES: int = 100` for `--lines`, and the plan gives no new name to either.
- The two renderers that gain the follow line are `src/devops_cli/roadmap/inbox.py:419:def _render_line(line: InboxLine) -> str:` and `src/devops_cli/roadmap/explain.py:336:def render_explanation(explained: Explanation) -> str:`, and neither sends a request for it. `explain` prints `explained.number`, the item's number.
- The pattern of the new command is `src/devops_cli/commands/roadmap.py:1045:@app.command("inbox", help=HELP.roadmap.inbox)` with `src/devops_cli/commands/roadmap.py:1046:@dry_run_class("request-plan")`, and the fake store appends one entry for each read at `tests/support/fakes/roadmap_store.py:739:self.reads.append("item")`, so the group 3 test asserts that the list is exactly `["item"]`.
- The calls that need a client: `store.item` needs a client of GitHub through the store, `log_tail` needs a client of the Kubernetes API built from the kubeconfig of the caller, and `_open_store` needs a client of GitHub. `follow_state`, `recorded_rows`, `render_recorded`, `live_lines`, `follow_command`, `summary_table`, `last_failing_command`, `decode`, `mask_secrets`, `explain_requests`, `_render_line` and `render_explanation` need no checkout, no client and no network.
- The plan introduces no program: its verifies are `uv run devops ci test`, `uv run devops ci docs` and `uv run devops openspec check`, and `uv`, `python`, `pytest`, `devops` and `openspec` are Runner tools of the image, so no tool is `NOT_IN_RUNNER`, no failure class is new, and the pod settings stay as they are.
- First checks against the real system: `uv run devops roadmap inbox` on a repository that holds one item prints the follow command of that item and none on a plan pull request line; `uv run devops ci test tests/roadmap/test_roadmap_follow_command.py`; `uv run devops openspec check`. The first manual run of the console reads the log of a running runner Job with a kubeconfig that may get and list pods and get pods/log.
- The rights of a person's kubeconfig on `pods/log` are not checked in this run: the plan changes no manifest, and the command reference states get and list on pods and get on pods/log, which a person confirms.

## Existing Tool Considered

kubernetes-client/python (Apache-2.0, maintained) reads the log of a Job pod through the cluster job API at `src/devops_cli/k8s/cluster_job_api.py:255:def log_tail(self, name: str, lines: int) -> str:`, so the live part adopts it and sends no GitHub request. The project builds the console around it at about 6,000 tokens to build, 1,500 tokens for each later fix, and about 1 day.

## Dependencies

None.
