# Tasks

## 1. One rule decides the open blockers of an item

Kind: behavior. Changes: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/test_roadmap_dependencies.py`, `tests/roadmap/refine/test_roadmap_dependency_graph.py`.

- [x] 1.1 Write the failing tests of the shared rule: the parent tracker and a tracker above the parent give no reason, another tracker gives its open sub-issues, a tracker with no open sub-issue gives none, a nested tracker gives the sub-issues of the inner tracker, the item is never its own blocker, and an open hold issue that is no tracker still holds the item. Write the failing graph tests: an edge to the parent tracker closes no cycle, an edge to another tracker leads through its open sub-issues, and a self-loop gives no path
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py tests/roadmap/refine/test_roadmap_dependency_graph.py` fails on the base
- [x] 1.2 Add `Item.parent` and `ItemTree` to the store, add `open_blockers` to `dependencies.py`, give `open_issue_dependencies` the item and the read, and build the edges of `DependencyGraph` with the rule. `DependencyGraph` keeps its tree as `tree`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dependencies.py tests/roadmap/refine/test_roadmap_dependency_graph.py`

## 2. Refine, stage and implement use the rule

Kind: behavior. Changes: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement.py`, `tests/roadmap/refine/test_roadmap_refine_blocked.py`, `tests/roadmap/refine/test_roadmap_refine_cycle.py`, `tests/roadmap/stage/test_roadmap_stage_selection.py`, `tests/roadmap/implement/test_roadmap_implement_selection.py`.

- [x] 2.1 Write the failing tests: a refine proposal that names the parent tracker reaches Ready, a proposal that names another tracker waits on its open sub-issues, a recorded wait on the parent tracker ends, a recorded wait on another tracker names its open sub-issues, an edge to the parent tracker gives no person step, the stage job stages an item whose body or record names its parent tracker, the stage reason names the open sub-issue of another tracker, and the implement job selects an item whose body or plan names its parent tracker
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_blocked.py tests/roadmap/refine/test_roadmap_refine_cycle.py tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/implement/test_roadmap_implement_selection.py` fails on the base
- [x] 2.2 Read the rule in `_open_dependencies` and `_open_blockers` of refine, with the tree of the round graph, in `_recorded_blocker` of the stage job, and in the plan check of the implement job. Delete `_is_open`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_blocked.py tests/roadmap/refine/test_roadmap_refine_cycle.py tests/roadmap/stage/test_roadmap_stage_selection.py tests/roadmap/implement/test_roadmap_implement_selection.py`

## 3. State the rule in the roadmap pages

Kind: other. Changes: `docs/roadmap/refine.md`, `docs/roadmap/stage.md`.

- [x] 3.1 State in `docs/roadmap/refine.md` and `docs/roadmap/stage.md` that the parent tracker and each tracker above it is no blocker, and that another tracker waits on its open sub-issues
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release, `devops roadmap explain 4909` gives no tracker as the reason, and the next refine round of #4671 records no `4624`.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
