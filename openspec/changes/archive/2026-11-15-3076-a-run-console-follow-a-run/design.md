# Design

## Decisions

- **Read the item once with `store.item` and take the trace, the runner Job name and the Job state from its job record.**: `read_trace` returns only the trace at `src/devops_cli/roadmap/explain.py:361:def read_trace(store: RoadmapStore, number: int) -> ImplementTrace | None:`, so a second read would double the one-request budget.
- **Render the rows of the console with `summary_table` and no second renderer.**: The issue requires the shape of the pull request comment, and one renderer cannot drift from itself.
- **Build the rows from the events of the recorded trace and parse no line of the pod log.**: The log holds tool-call lines and free notes and no step, check or attempt line, so a parser would read a note as a step.
- **Print the tail of the pod log of the runner Job with `log_tail` and mask each line with `mask_secrets`.**: The runner masks its own log lines with that function, so the console shows what the log shows and no secret.
- **Send one GitHub request, which reads the issue, and no other.**: The job record in the body holds the trace, the Job name and the Job state, and the live part reads the pod.
- **Take the default of `--lines` from `DEFAULT_LOG_TAIL_LINES` and give the bound no new name.**: The staged tree already holds the bound of a log tail, and a second name for it would drift.
- **Read the pod log with the kubeconfig of the caller and change no manifest.**: The command runs on a workstation, the Service account token is in the cluster, and the command reference states the three permissions that a person needs.
- **Format the follow command in one helper of `src/devops_cli/roadmap/follow.py` and call it from `inbox` and `explain`.**: Two copies of the text can drift, and one helper changes in one place.
- **Add the four message texts to `MESSAGES.roadmap` in the first group.**: One group writes the texts, so one existing test of the message module covers them and the later groups change no message.
- **Show the trace of the last run and no history of several runs.**: The record holds one trace, which a new run replaces; the plan promises no more and adds no second store.
- **Mark the lines that name an item with a new `item` field of `InboxLine`, and print the follow command from that field only.**: An inbox line's `number` is the pull request's for the plan, implement, release, draft and person lines at `src/devops_cli/roadmap/inbox.py:155:return InboxLine(kind, pull.number,`, so a follow command built from it would name a pull request number as an item.
- **Add no entry to the MCP exclusion table.**: The exposure test of `tests/ai/mcp/test_mcp_exposure_table.py` states that a new command needs no entry, so an exclusion group would change a test for no behavior.

## Rejected alternatives

- **Call `read_trace` and then read the item again for the runner Job.**: `read_trace` returns only the trace at `src/devops_cli/roadmap/explain.py:361:def read_trace(store: RoadmapStore, number: int) -> ImplementTrace | None:`, so the second read doubles the GitHub requests of a command whose budget is one.
- **Parse the free pod log into steps, checks and attempts.**: The only structured lines of the log are the tool-call lines, and the step rows come from the trace events, so a parser would report a note as a step.
- **Add a history store for past runs.**: The record keeps one trace at `src/devops_cli/roadmap/stores/store.py:396:TRACE = "implement.trace"` and replaces it when a run starts; a second store duplicates the record and adds a second source of run history.
- **Copy the table renderer into the console.**: `summary_table` already renders the table of the comment at `src/devops_cli/roadmap/implement/implement_trace.py:345:def summary_table(rows: Iterable[SummaryRow]) -> str:`, and a copy can drift from it.
- **Print the follow command from the number of every inbox line that has one.**: `src/devops_cli/roadmap/inbox.py:155:return InboxLine(kind, pull.number,` gives a plan, implement, release, draft or person line the number of a pull request, so that line would print a follow command for a pull request number.
- **Decide from the line's kind which numbers are item numbers.**: `InboxKind` is the display class and states no fact about the number: the item classes and the pull request classes would need a second list that stays in step with `src/devops_cli/roadmap/inbox_kind.py:class InboxKind`, and a new kind would silently gain or lose the follow line.
- **Read the live log with kubectl or stern.**: It adds a second process and a second log format to a command that already reads the log through the Kubernetes client.
- **Read pods/log with the token of the roadmap service.**: The command runs on a workstation and the Service account token lives in the cluster, so the caller's kubeconfig is the only access it has.

## Security

The console reads the log of a runner Job pod with the kubeconfig of the person who runs it and prints that text in a terminal, so a secret or a private host name in a log line would cross from the cluster to the workstation. A person must confirm that the kubeconfig in use may get and list pods and get pods/log in the namespace of the runner, and that each line passes the masking function of `src/devops_cli/security/sanitizer.py` before it is printed. `tests/roadmap/test_roadmap_follow_live.py` fails if a line reaches the output unmasked. No manifest changes, and the command never uses the token of the roadmap service.
