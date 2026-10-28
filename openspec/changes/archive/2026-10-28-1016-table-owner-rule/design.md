# Design

## Where the rule lives

`AGENTS.md` sends code conventions to `ARCHITECTURE.md` and `CONTRIBUTING.md`, and each rule lives in one document only. `CONTRIBUTING.md` already holds the parser rule ("Closed Lists and Standard Parsers") and the naming table, so the placement rule replaces the old bullet there. `docs/ROUTINE_TASKS.md` states the routine step and points to `CONTRIBUTING.md`.

## Decisions

- **Owner of a table that several modules of one package read**: the `constants.py` of that package, made when it is first necessary. This keeps the table in the package that owns it and keeps `config/` for names that two or more packages share.
- **Names**: PEP 8 constants. `_<NAME>` in the one module that reads it, `<NAME>` in a package's `constants.py`, so its sibling modules import a public name. `CONST_<NAME>` and `DEFAULT_<NAME>` stay the names of shared values in `config/`.
- **When a table moves**: when a change edits its owner, as the decision says. The items #1025 to #1032 move the tables of their packages before that.

## Rejected alternatives

- **A checker with a baseline** (`core/config_placement.py`, `tests/fixtures/config_placement_baseline.json` and two invariants in `tests/test_architectural_invariants.py`), from the 2026-10-17 plan of this item. The owner decision of 2026-10-22 rejected it: no gate checks the placement, and the project adds no ratchet.
- **The change to `DEFAULT_SANDBOX_POLICY`** that the second invariant needed. Without the invariant, nothing needs it.
- **Edits to `AGENTS.md`**. It holds no copy of the rule since its rewrite, and a second copy would break "each rule lives in one document only".
