# Design

## Decisions

- Require `registry: Sequence[RegistryCount]` as a keyword-only parameter without a default in `check_gates`, `check_proposal`, `replay_all`, and `replay_case`. Callers must supply the registry from the inspected checkout or test context.
- Add an ast-grep structural rule `stage-registry-cwd-read` in `.ast-grep/rules/stage-registry-cwd-read.yml` targeting `src/**` to enforce that no production code invokes `registry_table(Path.cwd())`.
- In `_Planner`, construct `self._registry = registry_table(source)` once during initialization and reuse it for all candidate items and gate checks.
- In `_Judge`, construct `_registry` once via `@cached_property` from `self._source`.
- In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, build the registry table once per pytest session using a session-scoped fixture `registry`.

## Rejected Alternatives

- Keep default `registry=None` falling back to `registry_table(Path.cwd())`: this was the source of defects when executing against external worktrees or isolated subdirectories.
- Recompute `registry_table` on every gate call: reading git and files repeatedly for every item and request wastes I/O and CPU cycles.
