# Proposal

## Why

Issue #1016: the documents told contributors to declare every list, tuple or frozen set that matches, classifies or filters values in `src/devops_cli/config/constants.py` or `src/devops_cli/config/defaults.py`. A table that one module reads then lives in a file of another package, far from its owner. The owner decided on 2026-10-22:

- A string table lives beside its one owner. It moves to `src/devops_cli/config/` only when a second package imports it.
- A maintained library or a language parser does the classification. A hand-written list is acceptable only for a closed domain that a standard defines.
- No constant moves in this change. A constant moves when its module is next changed.
- No gate checks the placement, and the project adds no ratchet.

## What Changes

- `CONTRIBUTING.md`, "Closed Lists and Standard Parsers": a matching table is a named module-level table beside its one owner, the module that reads it or the `constants.py` of its package. It moves to `config/` only when a module of a second package imports it. A change to the owner of a single-package table in `config/` moves the table to its owner.
- `CONTRIBUTING.md`, the Constant row of the naming table: `_<NAME>` in its one module, `<NAME>` in a package's `constants.py`, and `CONST_<NAME>` or `DEFAULT_<NAME>` in `config/` for a name that two or more packages import.
- `docs/ROUTINE_TASKS.md`: the routine-task matrix row, the flowchart step and step 3 of the inner loop state the same rule, and point to `CONTRIBUTING.md`.
- The change alters no behavior that a consumer observes: it changes two documents. So it has no spec delta and sets `skip_specs: true`.
- This change fits one pull request.

## Impact

- `CONTRIBUTING.md`, `docs/ROUTINE_TASKS.md`.
- The items that move single-owner tables out of `config/` (#1025 to #1032) follow this rule.

## Feasibility

Checked at `origin/main` daaffc62 on 2026-10-28:

- `AGENTS.md` (43 lines) holds no placement rule and no parser rule. It sends code conventions to `ARCHITECTURE.md` and `CONTRIBUTING.md`, and each rule lives in one document only. So the decision's edits to `AGENTS.md` (one parser bullet, the duplicate bullet deleted, a shorter file) are already in place, and this change does not edit `AGENTS.md`.
- The parser rule of the decision is in `CONTRIBUTING.md`, "Closed Lists and Standard Parsers", lines 17 to 19.
- `src/devops_cli/ai/instruction_generator.py` writes no placement rule into the files it generates, and `RELEASE_CYCLE.md` no longer states the rule (`git grep` for `constants.py`, `defaults.py` and "centralize").
- The old rule stayed in `CONTRIBUTING.md:20` and `:124`, and in `docs/ROUTINE_TASKS.md:28`, `:71` and `:87-90`. After this change, `git grep` finds no document that tells readers to declare every table in `config/constants.py` or `config/defaults.py`.
- No test and no ast-grep rule checks where a table is declared (`git grep` in `tests/`, `sgconfig.yml` and `src/`). So no check contradicts the new rule, and the decision adds none.

## Existing Tool Considered

The decision adds no check, so the change builds and uses no tool. An audit of the matching tables is a search for module-level upper-case collections over `src/devops_cli` with `rg`, which finds the tables in every package, not only in `config/`. The change deletes no code.
