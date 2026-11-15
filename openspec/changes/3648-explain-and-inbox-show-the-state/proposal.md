# Proposal

## Why

`devops roadmap explain` and `devops roadmap inbox` name only the step that stopped an item, so a person reads the stop comment to learn the class, the attempts, the kept work and the next action (#3648). The job computes the action left at the stop and records it nowhere, and `_blocked_line` prints one clear text for every class.

## What Changes

- Add `ImplementRecordKey.LEFT_ACTION` (`implement.left_action`) to `src/devops_cli/roadmap/stores/store.py`, write it in the marks of the stop in `src/devops_cli/roadmap/implement/implement_run.py`, clear it on the retry path of that module, and name it in the record key table of `docs/ROADMAP_WORKFLOW.md` and in the reader table of `tests/roadmap/implement/test_roadmap_implement_record_readers.py`.
- Clear `implement.left_action` in `_marks` of `src/devops_cli/roadmap/stop_clear.py`, which every clear rule of the Service writes through.
- Add `src/devops_cli/roadmap/stop_state.py`, which reads the step, the class, the attempts, the kept work and the action left of one item from its job record, with no client and no network.
- Print the state of a stop in `render_explanation` of `src/devops_cli/roadmap/explain.py`, from the item that `explain_item` reads already.
- Name the class, the attempts and the action left on the line of a stopped item in `_blocked_line` of `src/devops_cli/roadmap/inbox.py`, from the job record that the listing read, and prove the request count at the `gh` edge with two repositories built from `GitHubFake`, each with one open issue that holds `priority/p2-medium` and `status/blocked`.
- Add the texts of the new output to `src/devops_cli/lang/en/messages.py`.
- State the new output in `docs/ROADMAP_WORKFLOW.md` and in the help of the two commands in `src/devops_cli/lang/en/help.py`.
- Regenerate `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md` from the changed help.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-explain`: Explain names the state of a stopped item
- `roadmap-implement-job/stops`: The stop records the action left in the record, A retry and a clear rule remove the action left with the stop
- `roadmap-inbox`: The inbox line names the class and the action left of a stop, The inbox line states the attempts of a stopped step, The inbox line of a stop with no class on record, The inbox line of a stop adds no read

## Impact

- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stop_state.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/lang/en/help.py`
- Documents: `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`
- Tests: `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_record_readers.py`, `tests/roadmap/test_roadmap_stop_clear.py`, `tests/roadmap/test_roadmap_stop_state.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_inbox.py`, `tests/roadmap/test_roadmap_inbox_requests.py`, `tests/roadmap/test_roadmap_command_help.py`

## Feasibility

- The `probes` line "The path `src/devops_cli/roadmap/inbox.py` is a file of the staging commit." confirms the file that the issue cites, and the `read_file` of `src/devops_cli/roadmap/inbox.py` in this run showed `src/devops_cli/roadmap/inbox.py:201:stopped = item.job_record.get(ImplementRecordKey.STOPPED)` as the only source of the blocked line, so the premise of #3648 holds at the staged commit.
- The `search_code` for `"stopped":` answered `src/devops_cli/lang/en/messages.py:5444:"stopped": "{title}: stopped at {step}",` and `src/devops_cli/lang/en/messages.py:5488:Fix the cause, then comment`, so one subject and one clear text serve every class.
- The `probes` lines "The path `implement.stopped` is no file of the staging commit." and the same line for `implement.failure`, `implement.check` and `implement.wip` name record keys, not paths: the `read_file` of `src/devops_cli/roadmap/stores/store.py` in this run showed `src/devops_cli/roadmap/stores/store.py:388:STOPPED = "implement.stopped"`, `src/devops_cli/roadmap/stores/store.py:389:FAILURE = "implement.failure"`, `src/devops_cli/roadmap/stores/store.py:393:WIP = "implement.wip"` and `src/devops_cli/roadmap/stores/store.py:400:TRACE = "implement.trace"` as members of `ImplementRecordKey`, so no cited identifier is missing.
- `implement.left_action` is the key that this change creates, so no commit held it and it is no false premise; `read_file` of `src/devops_cli/roadmap/implement/implement_run.py` in this run showed `src/devops_cli/roadmap/implement/implement_run.py:2133:{"group": commit.group, "done": commit.done, "of": commit.total, "sha": commit.sha}`, the value of `implement.wip` that the report reads.
- The issue cites `src/devops_cli/roadmap/implement_run.py`, which is no file of the staged commit: the `read_file` of that module showed it at `src/devops_cli/roadmap/implement/implement_run.py:2015:ImplementRecordKey.STOPPED: stop.step,` in the marks of the stop, and the plan changes it at that path.
- `src/devops_cli/roadmap/implement/implement_run.py:1983:left = stop.action_left if stop.action_left is not None else left_action(klass, taken)` and `src/devops_cli/roadmap/implement/implement_run.py:2016:ImplementRecordKey.FAILURE: klass.value,` show that the stop computes the action left and records the class alone, so the new key is written beside the class in the same marks.
- `src/devops_cli/roadmap/implement/implement_run.py:795:marks[ImplementRecordKey.STOPPED] = None` is the retry mark of `_start`, so group 1 clears the new key beside it, and `src/devops_cli/roadmap/stop_clear.py:319:ImplementRecordKey.STOPPED: None,` sits in the one dict of `_marks` that every clear rule writes through, beside `src/devops_cli/roadmap/stop_clear.py:321:ImplementRecordKey.CHECK: None,`, so group 2 adds the new key there.
- The `read_file` of `src/devops_cli/roadmap/explain.py` in this run showed `src/devops_cli/roadmap/explain.py:98:class Explanation:`, whose `src/devops_cli/roadmap/explain.py:113:def as_dict(self) -> dict[str, object]:` returns its keys one by one, so a new field adds no key to the JSON object of `explain --json`, and `src/devops_cli/roadmap/explain.py:346:def render_explanation(explained: Explanation) -> str:` is where group 3 appends the lines of the stop.
- `src/devops_cli/roadmap/follow.py:93:attempts = [event for event in events if event.kind is TraceEventKind.ATTEMPT]` counts the attempt events of one step, and `src/devops_cli/roadmap/follow.py:82:def recorded_rows(trace: ImplementTrace) -> list[SummaryRow]:` groups the events by their step, so the attempts of the stopped step come from `implement.trace` with no second count key; `src/devops_cli/roadmap/implement/implement_trace.py:269:def decode(text: str) -> ImplementTrace:` reads that value and `src/devops_cli/roadmap/implement/implement_trace.py:67:ATTEMPT = "attempt"` is the kind that the count names.
- `tests/roadmap/implement/test_roadmap_implement_record_readers.py:72:assert {key.value for key in ImplementRecordKey} == set(READERS)` fails for a new member with no reader, and the table is `tests/roadmap/implement/test_roadmap_implement_record_readers.py:26:READERS: Final[dict[str, tuple[str, ...]]] = {`, so group 1 adds the entry in the same step as the enum member.
- The `search_code` for `record key {key} is missing` answered `tests/invariants/test_roadmap_workflow_doc.py:158:problems += [f"record key {key} is missing" for key in sorted(RECORD_KEYS - named_keys)]`, and the `read_file` of `docs/ROADMAP_WORKFLOW.md` in this run showed `docs/ROADMAP_WORKFLOW.md:167:The work in progress that a step kept`, so group 1 writes the new row with the key in a code span.
- `tests/roadmap/implement/test_roadmap_implement_job.py:751:item, {ImplementRecordKey.STOPPED: "group 2", ImplementRecordKey.FAILURE: "types"}` shows that the retry case seeds no `implement.left_action`, so group 1 seeds that key with `wait` in the same `set_marks` call and asserts that the retry leaves none of the three keys.
- `tests/support/roadmap_github_store.py:109:def seeded(**issues: tuple[str, ...]) -> tuple[GitHubFake, GitHubRoadmapStore]:` takes labels only, and `tests/support/roadmap_github_store.py:113:github.seed_issue(int(key.removeprefix("i")), labels=labels, body="Text")` writes a fixed body, so the request case builds each repository itself, with `GitHubFake(REPO, files={CONST_ROADMAP_LABELS_PATH: LABELS})`, `seed_label`, `seed_issue` with `body=with_record("", encode_job_record({}, marks))` and `tests/support/roadmap_github_store.py:104:def fake_store(github: GitHubFake) -> GitHubRoadmapStore:`.
- `tests/support/fakes/github_repository.py:63:files: dict[str, str | tuple[int, str]] | None = None,`, `tests/support/fakes/github_repository.py:106:body: str = "",` and `tests/support/fakes/github_repository.py:217:def seed_label(self, name: str, color: str, description: str | None = "") -> None:` show that the fake holds the labels file, the record body and the repository labels that the request case seeds, so the two runs need no change to `tests/support/roadmap_github_store.py`.
- `tests/support/fakes/github_repository.py:287:self.calls.append(args)` records every request at the `gh` process edge, so the request case counts them; the case cannot run over `tests/support/fakes/roadmap_store.py:646:def comments_on(self, number: int) -> list[IssueComment]:`, which records no read.
- The model review found that the request case seeded no Priority, and the `read_file` of `src/devops_cli/roadmap/stores/store.py` in this run showed `src/devops_cli/roadmap/stores/store.py:975:if item.priority is not None`, while `src/devops_cli/roadmap/stores/github_store.py:796:return select_items(self._read_issues("state=open"))` builds the inbox listing through it, so an issue with `status/blocked` alone is no Item and the case now seeds `priority/p2-medium` beside `status/blocked` and asserts that each run holds one blocked line.
- The `read_file` of `tests/roadmap/test_roadmap_inbox.py` in this run showed `tests/roadmap/test_roadmap_inbox.py:63:fields={ItemField.PRIORITY: "P2-Medium", **(fields or {})},`, so the case of a blocked item seeds a Priority on its issue, and the request case seeds that label in the same way.
- The constant that the request case needs is `src/devops_cli/config/constants.py:3894:CONST_ROADMAP_LABELS_PATH: Final[str] = ".github/labels.yml"`, and the constant of the clear text is `src/devops_cli/config/constants.py:3640:CONST_ROADMAP_IMPLEMENT_RETRY_COMMENT: Final[str] = "implement: retry"`. The plan adds no constant and no bound.
- `tests/roadmap/test_roadmap_limit_classes.py` declares the `CONST_ROADMAP_` prefix of that labels-file constant in its `REGISTRY_COUNTS` table, so the stage registry gate matches the plan: group 4 reads that test and names its declared path in the task text, and the plan adds no counted constant, because both cited constants exist at the staged commit.
- `src/devops_cli/roadmap/failure.py:368:return FailureAction.WAIT if taken is default else default` shows that the default action of a class is not the action left, so the plan records the value that the stop computes and reads no table.
- The first check against the real system is `uv run devops roadmap explain <issue-number>`, which needs a checkout of the repository, a client of GitHub and a network, for an open item that stops after this change: the report must name the class, the attempts, the kept work and the action left.
- The next check is `uv run devops roadmap inbox --repo <owner>/<name>`, which needs a client of GitHub and a network: the blocked line must name the class and the action left, and must state no count for one attempt. The `search_code` for `roadmap inbox` answered `docs/CLI_REFERENCE.md:317:| | `devops roadmap inbox [OPTIONS]` |`.
- `explain_item` of `src/devops_cli/roadmap/explain.py` needs a checkout of the repository and a client of the roadmap store; `read_inbox` of `src/devops_cli/roadmap/inbox.py` needs a client of the roadmap store; `stop_state_of` takes the `Item` that the caller read already and needs no checkout, no client and no network.
- The plan introduces no program: each `verify` runs `uv run devops ci test`, `uv run devops ci docs` or an existing test module. The runner image holds `uv`, `devops`, `pytest` and `git`, so no program is `NOT_IN_RUNNER`, and a failing case stops the step with the failure class `test`. The pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `capabilities.drop: ALL` and `allowPrivilegeEscalation: false`.

## Existing Tool Considered

No open, maintained tool or library covers this need: the output is this project's own job record and its failure classes, and no outside tool reads them. The change extends the code that exists, in `src/devops_cli/roadmap/inbox.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/roadmap/stop_clear.py`, `src/devops_cli/roadmap/stores/store.py` and `src/devops_cli/roadmap/implement/implement_run.py`. Cost: about 120k tokens to write, about 20k tokens a year to keep and fix, and about 3 hours of elapsed work. It adds no dependency.

## Dependencies

- #5786: changes `src/devops_cli/lang/en/messages.py`, the file that this change also changes for the new texts of the two commands.
- #5834: changes `src/devops_cli/lang/en/messages.py`, the file that this change also changes for the new texts of the two commands.
