# Proposal

## Why

No roadmap job checks the declared dependencies of an item for a cycle (#6449). Item A waits on B and B waits on A, so refine records `blocked` on each, the stage and implement reasons say only that the item depends on an open issue, and both items wait with no end. Six groups of open items sit in one, and a person sees the cycle only by following the links by hand.

## What Changes

- Add `DependencyGraph`, `cycle_text` and `_path_back` to `src/devops_cli/roadmap/refine/refine.py`: the edges that the job record, the Dependencies section and the quoted titles of each open item declare, gated once by `TopologicalSorter`, with a path back to each item that a dependency leads back to.
- Give `open_dependency` in `src/devops_cli/roadmap/dependencies.py` the cycle reason before the open-issue reason, with the message `dependency_cycle` in `src/devops_cli/lang/en/messages.py`, so the stage and implement call sites name the cycle unchanged.
- Give an item in a cycle the step `person` before the `ready` step of its proposal, with the cycle in its detail and in the Suspected block part of refine's section.
- Give `check_ready` the required keyword `cycle` and make it false for an item in a cycle, so refine writes no Ready Status for an item whose step is `person`, and a Ready item in a cycle goes back to New.
- Give `_still_waiting` the keyword `graph`, which defaults to none and is built from `store.items()` when `devops roadmap explain` or `select_candidates` gives none, and end the recorded wait of a `blocked` item that the graph holds in a cycle.
- Build one graph for each refine round in `_select_round` from the milestone items and backlog items that the round already read, and give it to the selection, so the round sends no store or GitHub request for it.
- Take the cycle of one item in `refine_one_item` from the listing that the function already reads for `title_dependencies`, so the round sends no second listing read.
- Keep the step `blocked` for an open dependency that is in no cycle.
- Add tests for the graph, the shared reason, the stage and implement reasons, the refine round over a store where the record of A names B and the Dependencies section of B names A, and `refine_left_out`, including the Status that the round leaves.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-dependency-cycle`: The dependency graph names a cycle for each item, The shared dependency reason names a dependency cycle

### Modified Capabilities

- `roadmap-refine/waits`: A dependency cycle gives a person step that names it, A cycle keeps an item out of Ready and ends its wait, An open dependency outside a cycle blocks the item

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/refine/test_roadmap_dependency_graph.py`, `tests/roadmap/test_roadmap_dependencies.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/refine/test_roadmap_refine_cycle.py`, `tests/roadmap/refine/test_roadmap_refine_proposal.py`

## Feasibility

- The review finding holds: `read_file` of `src/devops_cli/roadmap/refine/refine.py` lines 2790-2905 showed `src/devops_cli/roadmap/refine/refine.py:2809:selection = _Selection(store)` in `refine_left_out` and `src/devops_cli/roadmap/refine/refine.py:2859:selected, waiting, _ = _select_round(store, item_number=item_number, limit=limit, actor=actor)` in `select_candidates`, and `src/devops_cli/roadmap/refine/refine.py:2785:waits = _still_waiting(self.store, item, self.comments_on, self.questions())` as the one call of `_still_waiting`. The plan gives `_still_waiting` the keyword `graph`, which defaults to None and is built from `store.items()` inside its `BLOCKED` branch when the caller gives none, so `refine_left_out` and `select_candidates` run with no graph and `devops roadmap explain` ends the same wait that a round ends.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:2803:cannot differ (#3483). The limit of a round is no rule of the item.`: `refine_left_out` judges the item with the rules of the round, so explain must end the wait that the round ends, and the plan changes `refine_left_out` through `_still_waiting` and not by a copy of the rule.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:2880:milestone_items = [store.items(milestone=m.number) for m in open_milestones]` and `src/devops_cli/roadmap/refine/refine.py:2881:backlog_items = store.backlog()`: `_select_round` already reads every open item of the round, so the graph is built from that listing and the round sends no request for it.
- `search_code` for `def _select_single_candidate` showed `src/devops_cli/roadmap/refine/refine.py:2162:def _select_single_candidate(`: the `--item` path selects the item and calls no `_still_waiting`, so it needs no graph.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:3251:unmatched = title_dependencies(current_body, store.items()).unmatched` inside `refine_one_item`, which `search_code` gave at `src/devops_cli/roadmap/refine/refine.py:3152:def refine_one_item(`: the item already reads the listing there, so its cycle comes from that read and adds no request.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:3996:if r.is_ready:`, the statement that writes the Status Ready, and `src/devops_cli/roadmap/refine/refine.py:3256:proposal_ready = check_ready(proposal, open_questions, blockers)`, so `is_ready` is computed apart from `next_step_of`. The plan makes `check_ready` false for an item in a cycle, so the step `person` and the Status agree.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:1481:if not proposal.fits_one_pr or blockers:`, the statement that refuses Ready for an open dependency: the cycle takes the same path, with the required keyword `cycle` of `check_ready`, and the item stays New.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:1520:if is_ready:` and `src/devops_cli/roadmap/refine/refine.py:1527:return NextStep.BLOCKED, tuple(f"#{dep}" for dep in blockers), blockers`: the cycle branch goes before both, so an item in a cycle records `person` and names no open issue as its blocker.
- `search_code` for `check_ready(` showed `src/devops_cli/roadmap/refine/refine.py:1473:def check_ready(` as the one production definition and the call at `src/devops_cli/roadmap/refine/refine.py:3256:proposal_ready = check_ready(proposal, open_questions, blockers)` as its one production caller, and `tests/roadmap/refine/test_roadmap_refine_proposal.py:144:check_ready(base, [], ()),` as the test cases that group 5 updates with `cycle=False`.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:1501:return tuple(dep for dep in proposal.dependencies if _is_open(store, dep))`: the round keeps the open dependencies of the proposal and reads no dependency of those issues.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:1707:_PART_OPEN_QUESTIONS if open_questions else _PART_SUSPECTED_BLOCK,`: the Suspected block part is the part of a wait on a person that holds no open question, so the cycle line goes there and the wait names it.
- `read_file` showed `src/devops_cli/roadmap/refine/refine.py:2586:case NextStep.BLOCKED:` and `src/devops_cli/roadmap/refine/refine.py:2555:def _still_waiting(`: an unchanged blocked item is left waiting while its blocker is open, so the plan ends that wait when the item is in a cycle.
- `search_code` for `def recorded_blockers` showed `src/devops_cli/roadmap/refine/refine.py:def recorded_blockers`, and `read_file` showed `src/devops_cli/roadmap/refine/refine.py:2194:recorded = item.job_record.get(RefineRecordKey.BLOCKED_BY) or ""`: the key is a field of the item record and an edge of the graph. The probe reports "The path `refine.blocked_by` is no file of the staging commit. No commit in the history deleted or renamed it.", so the issue names a record key and no path.
- `read_file` showed `src/devops_cli/roadmap/dependencies.py:13:from devops_cli.roadmap.refine.refine import body_dependencies, title_dependencies` and the symbol `src/devops_cli/roadmap/dependencies.py:def open_dependency`: the shared read answers with the open-issue reason and names no cycle, and the item sequence that it already receives holds the edges that the graph needs.
- `read_file` showed `src/devops_cli/roadmap/stage/stage.py:774:return open_dependency(item, self._store, self._items)`, the one call site of the stage job, and `src/devops_cli/roadmap/stage/stage.py:769:return self._store.items()` under `@cached_property`: the job reads its listing once and holds it, so the graph adds no request.
- `read_file` showed `src/devops_cli/roadmap/implement/implement.py:382:return open_dependency(item, self._store, self._items)`, the one call site of the implement job, and `src/devops_cli/roadmap/implement/implement.py:372:return self._store.items()` under `@cached_property`: one change in the shared read reaches both jobs, and neither sends a request for the graph.
- `search_code` for `stage_left_dependency` showed `src/devops_cli/lang/en/messages.py:4245:stage_left_dependency: str = "The item depends on the open issue {issues}."`, the message that the plan puts `dependency_cycle` beside.
- The context of `src/devops_cli/core/import_graph.py` showed `from graphlib import CycleError, TopologicalSorter`: the repository already imports the sorter for its import graph, so the change adds no dependency.
- `DependencyGraph.of`, `cycle_text`, `_path_back`, `check_ready`, `_still_waiting` and `render_proposal_section` need no checkout, no client and no network.
- `open_dependency` needs a client of the roadmap store: the group 2 test gives it the in-memory fake store of `tests/support/roadmap_refine.py`, and the call reaches no network.
- `plan_refine` and `refine_one_item` need a checkout of the repository and a client of the LLM service: the group 5 test gives the refine round the checkout fixture and a fake model, and reaches no network.
- The first checks of the implementation are `uv run devops ci test tests/roadmap/refine/test_roadmap_dependency_graph.py`, then `uv run devops ci test tests/roadmap/test_roadmap_dependencies.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py`, `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py`, `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_cycle.py` and `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_proposal.py`.
- The plan introduces no command and no program of its own, so it needs no failure class of its own: `uv`, `devops` and `pytest` come from the runner image, no tool of the `NOT_IN_RUNNER` list is needed, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- not checked: the live graph of the 778 open issues and the six cycles of the issue body, because this run reads no GitHub state; the plan proves the rule on the in-memory store.

## Existing Tool Considered

`graphlib.TopologicalSorter` of the Python standard library, which the repository already imports for its import graph and which the alternatives block of the issue gives the verdict `in-use`. It finds a cycle and names its path; the change adds about 70 lines of adapter and no dependency.

## Dependencies

None.
