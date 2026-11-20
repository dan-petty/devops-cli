# Proposal

## Why

No roadmap job checks the declared dependencies of an item for a cycle (#6449). When item A waits on B and B waits on A, refine records the step `blocked` on each item, and the stage and implement reasons say only that the item depends on an open issue, so both items wait with no end and no inbox line names the cycle. Six groups of open items are in one, and a person sees it only by following the links by hand.

## What Changes

- Add `DependencyGraph`, `cycle_text` and `_path_back` to `src/devops_cli/roadmap/refine/refine.py` beside `body_dependencies`: the open items as nodes, the edges of the job record, the Dependencies section and the quoted titles, one `TopologicalSorter` gate, and a path back to each item that a dependency leads back to.
- Build one graph for each round in `plan_refine` from the open items that the round already reads for the owner-question frames, through the new `frames_of`, and give it to the selection and to each `refine_one_item` call, so the round reads no item listing for the graph.
- Give `open_dependency` in `src/devops_cli/roadmap/dependencies.py` the cycle reason after the open-issue reason, with the message `dependency_cycle` in `src/devops_cli/lang/en/messages.py`, so the stage and implement call sites name the cycle unchanged.
- Give an item in a cycle the step `person` first in `next_step_of`, with the cycle in the step detail and under the Suspected block heading of refine's section.
- Give `check_ready` the keyword `cycle` and make it false for an item in a cycle, so refine writes no Ready Status for an item that a cycle holds back.
- End the recorded blocked wait of an item in a cycle, so `devops roadmap explain` gives the answer that the round gives.
- Keep the step `blocked` for an open dependency that is in no cycle.
- Add the tests: the graph with its shared-edge, dropped-edge and closed-dependency cases, the shared reason, the stage reason, the implement reason, and the round over a store where the record of A names B and the Dependencies section of B names A.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-dependency-cycle`: The dependency graph names a cycle for each item, The shared dependency reason names a dependency cycle, The round builds one graph from the listing it already reads

### Modified Capabilities

- `roadmap-refine/waits`: A dependency cycle gives a person step that names it, A cycle keeps an item out of Ready and ends its wait, An open dependency outside a cycle blocks the item

## Impact

- Code: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/refine/test_roadmap_dependency_graph.py`, `tests/roadmap/test_roadmap_dependencies.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`, `tests/roadmap/refine/test_roadmap_refine_cycle.py`, `tests/roadmap/refine/test_roadmap_refine_proposal.py`

## Feasibility

- `probes` answers the cited identifier with: The path `refine.blocked_by` is no file of the staging commit. No commit in the history deleted or renamed it.
- `read_file` showed the read that the issue names at `src/devops_cli/roadmap/refine/refine.py:1498:def _open_dependencies(store: RoadmapStore, proposal: RefinementProposal) -> tuple[int, ...]:`, which keeps each open dependency of the proposal and looks at no dependency of that dependency.
- `read_file` showed the branches that answer before any cycle rule at `src/devops_cli/roadmap/refine/refine.py:1520:if is_ready:` and `src/devops_cli/roadmap/refine/refine.py:1527:return NextStep.BLOCKED, tuple(f"#{dep}" for dep in blockers), blockers`.
- `read_file` showed the one shared reason at `src/devops_cli/roadmap/dependencies.py:30:def open_dependency(item: Item, store: RoadmapStore, items: Sequence[Item]) -> str | None:` and its open-issue text at `src/devops_cli/roadmap/dependencies.py:27:return MESSAGES.roadmap.stage_left_dependency.format(issues=", ".join(open_issues))`.
- `read_file` showed that the round reads every open item before the selection at `src/devops_cli/roadmap/refine/refine.py:1559:for item in sorted(store.open_items(), key=lambda open_item: open_item.number):` and holds the frames at `src/devops_cli/roadmap/refine/refine.py:3587:frames = recorded_frames(store)`.
- `read_file` showed the explain entry at `src/devops_cli/roadmap/refine/refine.py:2800:def refine_left_out(store: RoadmapStore, item: Item) -> str | None:` and the round's selection call at `src/devops_cli/roadmap/refine/refine.py:3589:candidates, waiting, queue = _select_round(`.
- `read_file` showed the blocked branch that keeps a wait at `src/devops_cli/roadmap/refine/refine.py:2586:case NextStep.BLOCKED:` and the record read it uses at `src/devops_cli/roadmap/refine/refine.py:2192:def recorded_blockers(item: Item) -> list[int]:`.
- `read_file` showed the three places that the cycle reaches at `src/devops_cli/roadmap/refine/refine.py:3256:proposal_ready = check_ready(proposal, open_questions, blockers)`, `src/devops_cli/roadmap/refine/refine.py:3279:step, model_details, blocked_by = next_step_of(` and `src/devops_cli/roadmap/refine/refine.py:3316:rendered_section = render_proposal_section(`.
- `read_file` showed the item record write at `src/devops_cli/roadmap/refine/refine.py:3372:is_ready=is_ready,` and the quoted-title parse that the graph also reads at `src/devops_cli/roadmap/refine/refine.py:1266:def title_dependencies(body: str, items: Sequence[Item]) -> TitleDependencies:`.
- `read_file` showed the Dependencies section parse at `src/devops_cli/roadmap/refine/refine.py:1224:def body_dependencies(body: str) -> list[int]:`, which the graph reads beside the record.
- `read_file` showed the sorter in use at `src/devops_cli/core/import_graph.py:18:from graphlib import CycleError, TopologicalSorter`, so the change adds no dependency.
- The two call sites that the change leaves as they stand are `src/devops_cli/roadmap/stage/stage.py:774:return open_dependency(item, self._store, self._items)` and `src/devops_cli/roadmap/implement/implement.py:382:return open_dependency(item, self._store, self._items)`, which hold the listing that the reason reads.
- `plan_refine` needs a checkout of the repository and a client of the LLM service: the group 5 test gives the round a repository fixture and a model fake through `tests/support/roadmap_refine.py:382:def refine_round(`, and reaches no network.
- `open_dependency` needs a client of the roadmap store: the group 2 test gives it the in-memory fake store of `tests/support/fakes/roadmap_store.py`, and the call reaches no network.
- `refine_left_out` needs a client of the roadmap store: the group 5 test gives it the same fake store, and the call reaches no network.
- `DependencyGraph.of`, `cycle_of`, `cycle_text`, `_path_back` and `frames_of` take an item sequence and need no checkout, no client and no network.
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/roadmap/refine/test_roadmap_dependency_graph.py`, `uv run devops ci test tests/roadmap/test_roadmap_dependencies.py`, `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_cycle.py`, `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_selection.py` and `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_selection.py`.
- The plan introduces no command and no program: `uv`, `devops` and `pytest` are in the runner image, no tool of the `NOT_IN_RUNNER` list is needed, and the pod keeps `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- not checked: the live graph of the 778 open issues and the six cycles of the issue body, because this run reads no GitHub state and runs no command; the plan proves the rule on the fake store.
- The earlier reply failed the check because its feasibility named modules with no full line of them and quoted no probe line. This reply quotes the probe line above, and names a module only inside a `path:line:text` code span that holds a complete line of that module.

## Existing Tool Considered

`graphlib.TopologicalSorter` of the Python standard library, which the repository already imports at `src/devops_cli/core/import_graph.py:18:from graphlib import CycleError, TopologicalSorter` and which the alternatives block of the issue records with the verdict in-use. It finds a cycle and names its path, so the change adds about 90 lines of adapter and no dependency.

## Dependencies

None.
