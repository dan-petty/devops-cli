# Design

## Decisions

### The cap is 4 nested blocks

At `max-nested-blocks = 4`, Ruff fails the same five-block `if`, `for`, `while`, `with` and `except` samples as the hook at `--max-depth 5`, and it fails five blocks with a `try` body that the hook passed. The 12 functions it found are each split with one helper, so no function changes what it returns or raises.

Rejected: 5, the value of the owner's 2026-10-22 decision. It allows a fifth block, one level looser than the hook. The decision allowed that change, but did not require it, and the coordinator asked for a cap at least as strict as the hook.

### Lint preview with explicit preview rules

`preview = true` and `explicit-preview-rules = true` under `[tool.ruff.lint]`, and `PLR1702` in `select`.

Rejected:
- `[tool.ruff] preview = true` or the `--preview` flag: they also set `formatter.preview`, which can change the formatted output of the whole tree.
- A second Ruff run that selects only `PLR1702` (fix C of the 2026-10-22 survey): it needs a second configuration or extra flags, and `tests/test_ruff_complexity_cap.py` pins every `ruff check` to `--config pyproject.toml` with no other flag.
- `per-file-ignores` for findings: a baseline, which the 2026-10-22 decision rules out, and the settings guard requires `linter.per_file_ignores = {}`.

Lint preview also turns on the preview behavior of stable rules. After #2010 the tree has no finding under it; a later preview change in Ruff shows in `ruff check` like any other finding.

### No nesting figure in product code

`PLR1702` gives no depth for each function, only a finding above the cap, and Ruff is a development dependency. So `devops scan complexity` and `devops ai spec` drop the figure (decision 3 of #1876).

Rejected: a Ruff subprocess in product code at the user's cap. It adds a runtime dependency on a development tool for a figure that `ruff check` already gates.

### The match gap stays

Rejected: an ast-grep rule for a `match` nested under four blocks. ast-grep has no depth count; a rule would chain one `inside` clause for each level and each block kind, a hand-written metric again. The gap is stated in the pull request and in `CONTRIBUTING.md`.
