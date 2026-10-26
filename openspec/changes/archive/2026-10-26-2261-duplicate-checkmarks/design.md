# Design

## Context

See proposal.md for motivation and problem background.
The `print_success` function in `src/devops_cli/output/console.py` prepends `"✓ "` by default when `prefix` is `True`.
Twenty-five callers in `src/devops_cli/commands/` passed messages starting with `"✓ "` or `"✓"`.
This caused duplicated check marks in console output.

## Goals / Non-Goals

**Goals:**

- Remove manual prefix symbols from message arguments at all call sites in `src/devops_cli`.
- Add an AST invariant test in `tests/test_output.py` that fails if any leveled print call passes a message starting with the prefix symbol of that level.
- Update documentation examples that model manual prefix inclusion.

**Non-Goals:**

- Adding automatic runtime prefix stripping in `console.py`. Callers must supply clean message strings directly.
- Modifying behavior when `prefix=False` is intentionally passed for custom indentation or custom icons.

## Decisions

### Decision: Remove prefixes from caller strings instead of adding runtime stripping

We strip the redundant prefix characters from callers in `src/devops_cli`.
We enforce this with an AST test rather than adding runtime regex or trimming in `console.py`.
Rationale: In accordance with Rule 2 of `AGENTS.md`, we write no compensating code.
Callers must provide correct inputs.
A static AST test prevents regressions without runtime overhead.

*Alternative considered: Runtime trimming in `print_message` / `print`.*
Rejected: Runtime trimming masks defects at call sites and adds string manipulation overhead to every console write.

### Decision: AST invariant test location in `tests/test_output.py`

We place the AST invariant test in `tests/test_output.py` using the session fixture `parsed_source_trees`.
Rationale: `test_output.py` owns unit and structural testing for the output subsystem.
Reusing `parsed_source_trees` avoids re-parsing Python source files.

*Alternative considered: Creating a new invariant test file in `tests/invariants/`.*
Rejected: The project convention stores output-related AST invariants in `tests/test_output.py` (e.g. `test_rich_imports_confined_to_output_submodule`).

## Risks / Trade-offs

- [Risk: Existing test assertions might match the double check mark `✓ ✓`] → Mitigation: We searched the entire test suite; no tests assert duplicated check marks.
- [Risk: New code could reintroduce duplicated prefixes] → Mitigation: The AST invariant test runs in CI and pre-push loops to prevent regressions.
