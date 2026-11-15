# Proposal

## Why

`devops roadmap explain` and `devops roadmap inbox` name only the step that stopped an item, so a person reads the stop comment to learn the class, the attempts, the kept work and the next action (#3648). The job computes the action left at the stop and records it nowhere, and `_blocked_line` prints one clear text for every class.

## What Changes

- Add `ImplementRecordKey.LEFT_ACTION` (`implement.left_action`) to `src/devops_cli/roadmap/stores/store.py` and write it in the marks of `stop` in `src/devops_cli/roadmap/implement/implement_run.py`, with the row of the record key table of `docs/ROADMAP_WORKFLOW.md` in the same group.
- Clear `implement.left_action` in the retry marks of `_start` of `src/devops_cli/roadmap/implement/implement_run.py` and in `_marks` of `src/devops_cli/roadmap/stop_clear.py`.
- Add `src/devops_cli/roadmap/stop_state.py`, which reads the step, the class, the attempts, the kept work and the action left of one item from its job record, with no client and no network.
- Print the state of a stop in `render_explanation` of `src/devops_cli/roadmap/explain.py`.
- Name the class, the attempts and the action left on the line of a stopped item in `_blocked_line` of `src/devops_cli/roadmap/inbox.py`, and prove the request count at the `gh` process edge over `GitHubFake`, against an item with no stop, in `tests/roadmap/test_roadmap_inbox_requests.py`.
- Add the texts of the new output to `src/devops_cli/lang/en/messages.py`.
- Name the new key in the record key table of `docs/ROADMAP_WORKFLOW.md` and state the new output in the page and in the help of the two commands.
- Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` from the changed help.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-explain`: Explain names the state of a stopped item
- `roadmap-inbox`: The inbox line names the class and the action left of a stop, The inbox line states the attempts of a stopped step, The inbox line of a stop with no class on record, The inbox line of a stop adds no read
- `roadmap-implement-job/stops`: The stop records the action left in the record, A retry and a clear rule remove the action left with the stop

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stop_state.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/test_roadmap_stop_state.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_command_help.py`

## Feasibility

- The `probes` line "The path `src/devops_cli/roadmap/inbox.py` is a file of the staging commit." and `src/devops_cli/roadmap/inbox.py:201:stopped = item.job_record.get(ImplementRecordKey.STOPPED)` show that the line of a stop reads the step alone, so the premise of the issue holds at the staged commit.
- `src/devops_cli/roadmap/inbox.py:204:subject = subjects["stopped"].format(title=item.title, step=stopped)` with `src/devops_cli/lang/en/messages.py:5444:"stopped": "{title}: stopped at {step}",` and `src/devops_cli/lang/en/messages.py:5488:"stopped": "Fix the cause, then comment `{retry}` on #{number}.",` show that one subject and one clear text serve every class.
- The `probes` lines "The path `implement.stopped` is no file of the staging commit. No commit in the history deleted or renamed it." and the same line for `implement.failure`, `implement.check` and `implement.wip` name record keys, not paths: `src/devops_cli/roadmap/stores/store.py:388:STOPPED = "implement.stopped"`, `src/devops_cli/roadmap/stores/store.py:389:FAILURE = "implement.failure"` and `src/devops_cli/roadmap/stores/store.py:393:WIP = "implement.wip"` are members of `ImplementRecordKey`, so no cited identifier is missing.
- The issue cites `src/devops_cli/roadmap/implement_run.py`, which is no file of the staged commit: `src/devops_cli/roadmap/implement/implement_run.py:2013:ImplementRecordKey.STOPPED: stop.step,` shows the module in the `implement/` subpackage, and the plan changes it at that path.
- `src/devops_cli/roadmap/implement/implement_run.py:1981:left = stop.action_left if stop.action_left is not None else left_action(klass, taken)` and `src/devops_cli/roadmap/implement/implement_run.py:2014:ImplementRecordKey.FAILURE: klass.value,` show that `stop` computes the action left and records the class alone.
- `src/devops_cli/roadmap/implement/implement_run.py:795:marks[ImplementRecordKey.STOPPED] = None` is the retry mark of `_start`, so group 1 clears the new key beside it, and `src/devops_cli/roadmap/stop_clear.py:319:ImplementRecordKey.STOPPED: None,` is in the one dict of `_marks` that every clear rule writes through, so group 2 adds the new key there.
- `src/devops_cli/roadmap/explain.py:346:def render_explanation(explained: Explanation) -> str:` appends the totals of the last run, so group 3 appends the lines of the stop there; the frozen `Explanation` gives a default to its later fields and `as_dict` returns its keys one by one, so a new field adds no key to the JSON object of `explain --json`.
- `src/devops_cli/roadmap/follow.py:93:attempts = [event for event in events if event.kind is TraceEventKind.ATTEMPT]` counts the attempt events of one step, and `recorded_rows` of `src/devops_cli/roadmap/follow.py` groups the events by their step, so the attempts of the stopped step come from the trace that `src/devops_cli/roadmap/implement/implement_trace.py:269:def decode(text: str) -> ImplementTrace:` reads, with no second count key.
- `tests/roadmap/implement/test_roadmap_implement_record_readers.py:72:assert {key.value for key in ImplementRecordKey} == set(READERS)` fails for a new member with no reader, so group 1 adds the entry `("text", DOCUMENT, "The action left with the stop")` in the same step as the enum member, and the doc row of group 1 holds that text.
- `tests/invariants/test_roadmap_workflow_doc.py:68:def _code_spans(tokens: list[Token]) -> set[str]:` and `tests/invariants/test_roadmap_workflow_doc.py:158:problems += [f"record key {key} is missing" for key in sorted(RECORD_KEYS - named_keys)]` read the record keys from inline code spans, and `docs/ROADMAP_WORKFLOW.md:167:| Implement | `implement.wip` | The work in progress that a step kept` shows that shape, so group 1 writes the new row with the key in a code span.
- The review finding on the request count is corrected: `tests/support/fakes/github_repository.py:287:self.calls.append(args)` records every request at the `gh` process edge, and `tests/support/fakes/github.py:560:reply = self._runner([f"{API}{path}"], check=False, quiet=True, use_cache=False)` shows that a listing lands in the same list, so the case of group 4 compares a blocked item that holds a stop against a second one-item repository whose item holds `status/ready` and no stop, and it fails when the new line reads one issue or its comments; the earlier shape compared two stopped items, which send the same stop read and could not fail.
- The case cannot run over the in-memory store: `tests/support/fakes/roadmap_store.py:646:def comments_on(self, number: int) -> list[IssueComment]:` returns the comments and `tests/support/fakes/roadmap_store.py:898:def _read(self, issue: IssueRecord) -> IssueRecord:` appends nothing to `reads`, so that store records no read of a stop, while `src/devops_cli/roadmap/stores/github_store.py:780:found = self._read_or_none(issue_args(self._repo, number), _ISSUE, f"issue #{number}")` shows that a read of one item is one request at the `gh` edge.
- `tests/roadmap/test_roadmap_run_github_requests.py:64:assert (ran, [args[-1].split("?")[0] for args in github.calls]) == (` is the pattern that module already uses to compare the paths of `github.calls` over `GitHubFake`, and `tests/support/fakes/github.py:539:class RunnerSession:` answers the listing of the store from the same runner, so the new case follows a shape that exists.
- `tests/roadmap/test_roadmap_inbox_requests.py:50:reads, writes = inbox_requests(REPO)` builds the static plan of the reads from `src/devops_cli/roadmap/request_plan.py` whatever `_blocked_line` does, so the new case does not use it; it runs `read_inbox`, as `tests/roadmap/test_roadmap_inbox.py:74:return read_inbox(` does, over two repositories of `GitHubFake`.
- `src/devops_cli/lang/en/help.py:2070:inbox: str = (` and `src/devops_cli/lang/en/help.py:1924:explain: str = (` hold the two helps, and `tests/roadmap/test_roadmap_command_help.py:16:MAX_SENTENCES = 3` bounds them, so group 5 rewrites one sentence of the inbox help and adds none.
- `src/devops_cli/roadmap/stop_state.py` and `tests/roadmap/test_roadmap_stop_state.py` are new files of this change, and `tests/roadmap/test_roadmap_explain.py:182:def test_a_stopped_item_names_its_stop_for_the_implement_job(job_world: JobWorld) -> None:` is the case that group 3 extends.
- The sample item of the issue is closed: `read_issue` of 2462 answered that the issue is closed, and `src/devops_cli/roadmap/explain.py:273:if item is None or item.state is not GitHubState.OPEN:` returns the refusal of a closed item, so the check against the real system uses an open item that stops after this change.
- The first check against the real system is `uv run devops roadmap explain <issue-number>`, with a client of GitHub, a network and a checkout of the repository, for an open item that stops after this change: the report must name the class, the attempts, the kept work and the action left.
- The next check is `uv run devops roadmap inbox --repo <owner>/<name>`, with a client of GitHub and a network: the blocked line must name the class and the action left, and must state no count for one attempt.
- `explain_item` of `src/devops_cli/roadmap/explain.py` needs a checkout of the repository and a client of the roadmap store; `read_inbox` of `src/devops_cli/roadmap/inbox.py` needs a client of the roadmap store; `stop_state_of` takes the `Item` that the caller already read and needs no checkout, no client and no network.
- The plan introduces no program: each `verify` runs `uv run devops ci test` or the existing `uv run devops ci docs` row, whose check is `src/devops_cli/commands/ci.py:932:cmd=["uv", "run", "devops", "docs", "check"],`. The runner image holds `uv`, `devops`, `pytest` and `git`, so no program is `NOT_IN_RUNNER`, and a failing case stops the step with the failure class `test`. The pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL` and `allowPrivilegeEscalation: false`.
- The plan adds no constant and no bound: `_blocked_line` keeps `CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT` and the trace keeps `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` of the staged tree, and `probes` holds no line for either, so their values are not checked and this plan gives them no new name.

## Existing Tool Considered

No open, maintained tool or library covers this need: the output is this project's own job record and its failure classes, and no outside tool reads them. The change extends the code that exists, in `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stores/store.py` and `src/devops_cli/roadmap/implement/implement_run.py`. Cost: about 120k tokens to write, about 20k tokens a year to keep and fix, and about 3 hours of elapsed work. It adds no dependency.

## Dependencies

- #5786: changes `src/devops_cli/lang/en/messages.py`, which this change also changes for the new texts of the two commands.
- #5823: changes `src/devops_cli/lang/en/messages.py`, which this change also changes for the new texts of the two commands.
