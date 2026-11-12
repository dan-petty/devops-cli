# Proposal

## Why

#1910 asks for a manual caller check of the symbols in `src` that only tests call. The vulture trial of #1871 listed 19 names. The CI audit of 2026-11-11 ran vulture again and found 129 symbols that only tests name, with 242 tests. Dead code costs a reader, a test run and a type check, and docs/TESTING.md says to delete a line that no public behaviour reaches.

## What Changes

- Read each of the 129 audit symbols and each name of the issue list. Delete a symbol when no module of `src`, no entry point, no framework hook, no document and no string calls it. Delete the tests whose subject is that symbol.
- Delete 75 of the 129 audit symbols and 11 names of the issue list. Delete the 3 modules that no module of `src` imports: `ai/agents/capabilities.py`, `k8s/chaos_runner.py` and `output/table_builder.py`.
- Delete the helpers, classes, constants, defaults and the tool message that only a deleted symbol used, such as the `Embedder` class, the domain schema hydrator and the lease renewal of the Vault registry. A second vulture run finds no new unused name in `src`.
- Move a test that checks live code through a deleted wrapper to the live function, for example `tally_findings`, `apply_branch_symbol_delta`, `why_not_on_merged_code`, `preload_models` and `_extract_structured_strings`.
- Keep 54 audit symbols, each with its reason in design.md: a framework hook, an invariant or gate helper, a test seam, new code that is not wired yet, a file that another open item changes, or a name that a spec or a standards document holds.
- Lower the swallowed-failures ceiling of `ai/review/pipeline.py` and drop the entries of the deleted modules.
- Add no vulture gate: vulture cannot see a framework hook, a registry entry or a string caller.
- Carry no spec delta: the change deletes code that no command, option, message or service reaches, so no consumer observes it.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: 52 files under `src/devops_cli`, 2043 lines deleted.
- Tests: 52 files under `tests`, 89 test cases fewer in the changed files, 12 tests renamed to the live function that they now call.

## Feasibility

- `uvx vulture src` (vulture 2.16) on the rebased branch, filtered as the audit script `dead_code_tests.py` filters it (no decorator, one occurrence of the name in `src`, a test that names it), gives 129 rows, the same count as the audit.
- `git grep -w -F <name>` on `src`, `docs`, the knowledge base, `pyproject.toml` and the workflows gave each decision. `pyproject.toml` names one entry point, `devops = "devops_cli.entry:main"`, so `main.main_entry` is no entry point.
- No module of `src` imports `devops_cli.ai.agents.capabilities`, `devops_cli.k8s.chaos_runner` or `devops_cli.output.table_builder` (`git grep` gives no line).
- After the deletions, a second vulture run gives no unused name that the first run did not give, except an enum member and two model fields that stay.
- `uv run mypy --python-version 3.14 --strict src` passes on 815 source files. The changed test files pass: 1264 tests.

## Existing Tool Considered

[vulture](https://github.com/jendrikseipp/vulture) is the open, maintained dead-code finder that made the candidate list. It cannot see a framework hook, a registry entry or a string caller, so the change reads each caller by hand and adds no gate. The change deletes internal code only and builds nothing.

## Dependencies

None.
