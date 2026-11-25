# Proposal: #5378

## Why
`devops openspec check` passes an active change whose spec delta holds a `MODIFIED` requirement longer than 500 UTF-16 code units (#5378). When `devops openspec archive` later merges that delta into the living specification, `openspec validate --all --strict` refuses the merged spec and leaves the archive applied on disk for manual repair.

## What Changes
Run the shared `REQUIREMENT_MAX_CHARS` length check on every `ADDED` and `MODIFIED` requirement of each active change inside `devops openspec check` before CLI validation runs.

- Expose `requirement_length_problem(name, text)` alongside `REQUIREMENT_MAX_CHARS` in `src/devops_cli/roadmap/stage/stage_change.py` and call it from `_length_problems`.
- Read active change deltas once per active change via `change_deltas` in `src/devops_cli/openspec/overlap.py`, feeding both the length check and the overlap check without running `openspec show` twice.
- Add `GateCheck.REQUIREMENT_LENGTH` in `src/devops_cli/openspec/gate.py` so `check_openspec` runs length checks before `_validation_findings` using the imported rule from `stage_change.py`.
- Defer importing `devops_cli.openspec.gate` inside `check` and `regenerate` in `src/devops_cli/commands/openspec.py` so `devops openspec --help` keeps `stage_change` and `pydantic_ai` out of CLI startup imports.

This changes observable CLI and CI behavior (`devops openspec check`, `devops ci --check --only openspec`, and `GateFinding` output), so it carries a spec delta for `openspec-check`. Fits in one pull request.

## Capabilities
- `openspec-check` (`openspec/specs/openspec-check/spec.md`)

## Impact
- `src/devops_cli/roadmap/stage/stage_change.py`: extracts public `requirement_length_problem`.
- `src/devops_cli/openspec/overlap.py`: adds shared delta reader `change_deltas` and `overlapping_deltas`.
- `src/devops_cli/openspec/gate.py`: adds `GateCheck.REQUIREMENT_LENGTH` and checks active deltas before CLI validation.
- `src/devops_cli/commands/openspec.py`: defers importing `openspec.gate` into command bodies to protect startup import budgets.
- `tests/openspec/test_openspec_gate.py`: adds offline contract tests covering all requirements.

## Feasibility
Confirmed against source and recorded OpenSpec fixtures on `origin/main`:
- `src/devops_cli/roadmap/stage/stage_change.py:140,947-963` defines `REQUIREMENT_MAX_CHARS = 500`, `_js_length` (UTF-16 LE code units), and `_length_problems` using `MESSAGES.roadmap.stage_problem_requirement_long`.
- `tests/fixtures/openspec_runs/recorded_runs.json` confirms `openspec show <change> --json --deltas-only` returns `deltas[]` objects with `operation`, `requirement.name`, and `requirement.text`.
- `src/devops_cli/commands/ci.py:1021` defines the `openspec` CI row as `["uv", "run", "devops", "openspec", "check"]`, so checking inside `check_openspec` enforces both `devops openspec check`, the CI row, and the pre-commit hook.
- Measuring `sys.modules` confirmed that top-level import of `stage_change` loads `pydantic_ai`, which `tests/gate/startup_imports.py:252` forbids on `devops openspec --help`; deferring the `gate` import inside `commands/openspec.py` avoids that load at help time.

## Existing Tool Considered
OpenSpec (`@fission-ai/openspec`, MIT, pinned at 2.1.0, actively maintained) covers schema validation, change delta extraction (`openspec show --json --deltas-only`), warnings on long `ADDED` requirements during change validation, and strict rejection of long spec requirements after archive. It lacks a pre-archive length check on `MODIFIED` requirements and does not emit the shared `stage_problem_requirement_long` finding naming the requirement and its UTF-16 length. Building an independent standalone limit or length calculator is rejected; instead we share `requirement_length_problem` from `stage_change.py` (~2k tokens, <1 hour) and eliminate duplicate inline formatting inside `_length_problems`.
