# tool-passthrough-registry Specification

## Purpose

Defines the pass-through tool registry (`src/devops_cli/core/passthrough.py`), never-wrapped `gh` verb constraints, and the architecture decision record for mirroring underlying CLI tool names, options, and API routes.

## ADDED Requirements

### Requirement: ADR records the pass-through rule in MADR 4 form
The project SHALL add the next free ADR (`0037`) in MADR 4 form under `docs/adr/`, recording the 2026-11-12 owner rule on #5223 that tool commands take the command names and options of the tool and pass arguments through, while API-based tool commands take API route names.

#### Scenario: ADR record and README index validate
- **WHEN** `uv run devops ci test tests/invariants/test_adr_records.py` and `uv run devops docs check` run
- **THEN** both exit 0 and `docs/adr/README.md` indexes ADR `0037`

### Requirement: Pass-through registry holds the gh run list entry
`devops_cli.core.passthrough.REGISTRY` SHALL map `'gh run list'` to a frozen `PassthroughEntry` with `devops_paths` containing `'devops gh run list'`, `runner` equal to `run_gh`, `mode` equal to `'read'`, non-empty `owned_options` and `refused_options`, positive `run_cost` and `timeout`, a `page_rule` naming `'-L'` and `'--limit'`, and an `mcp_allowlist` whose entries each define `arity` and `cap` and belong to `owned_options`.

#### Scenario: Registry entry exposes complete typed contract
- **WHEN** `tests/core/test_passthrough.py` inspects `REGISTRY['gh run list']`
- **THEN** every required field and invariant holds

### Requirement: Never-wrapped gh verbs are excluded from the registry
`devops_cli.core.passthrough.NEVER_WRAPPED` SHALL equal `{'pr merge', 'auth', 'secret set', 'repo delete', 'release'}`, and no key in `REGISTRY` (with or without a leading `'gh '` prefix) MAY equal or begin with any listed verb plus a space.

#### Scenario: Never-wrapped list stays enforced
- **WHEN** `tests/core/test_passthrough.py` checks `NEVER_WRAPPED` against all `REGISTRY` keys
- **THEN** all five verbs are present in `NEVER_WRAPPED` and zero registry entries match a never-wrapped verb

### Requirement: Registered devops paths resolve in the CLI tree
Every command string in `devops_paths` for every entry in `REGISTRY` SHALL resolve to a registered command via `resolve_devops_argv`.

#### Scenario: All entry devops paths resolve
- **WHEN** `tests/core/test_passthrough.py` resolves each path in every `REGISTRY` entry
- **THEN** `resolve_devops_argv` returns `None` for every path
