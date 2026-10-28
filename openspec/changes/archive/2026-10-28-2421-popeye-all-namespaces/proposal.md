# Proposal

## Why

Issue #2421: `build_popeye_cmd` and `PopeyeScanner.build_command` omit the `-A` (`--all-namespaces`) flag when `namespace` is None. Popeye 0.22.1 then scans only the namespace of the current context instead of every namespace. Security findings in other namespaces go undetected when no namespace is specified.

## What Changes

- `build_popeye_cmd` adds `-A` when `namespace` is None or empty.
- When `namespace` is provided, `build_popeye_cmd` includes `-n <namespace>` and no `-A`.
- The `scanner-adapters` spec updates its requirement and scenario to specify that Popeye runs with `-A` when given no namespace.
- Tests in `tests/test_command_builders.py` and `tests/test_secops.py` verify that `build_popeye_cmd` and `run_popeye_scan` include `-A` when no namespace is given.
- The change fits in one pull request.

## Capabilities

### New Capabilities

### Modified Capabilities

- `scanner-adapters`: Popeye runs with `-A` when it gets no namespace.

## Impact

- `src/devops_cli/config/commands.py` (`build_popeye_cmd`).
- `openspec/specs/scanner-adapters/spec.md`.
- `tests/test_command_builders.py` and `tests/test_secops.py`.

## Feasibility

Confirmed against Popeye 0.22.1 (`popeye --help`):
`-A, --all-namespaces` runs linters for all namespaces. `-n, --namespace string` specifies the namespace scope. `build_popeye_cmd` without `namespace` currently emits `popeye -o json -l warn`, which defaults Popeye to the namespace of the context. Adding `-A` when no namespace is specified instructs Popeye to scan all namespaces across the cluster.

## Existing Tool Considered

Popeye 0.22.1 is already integrated in `tools.lock` and `src/devops_cli/security/popeye.py`. The change uses Popeye's standard `-A` flag. It builds no new tool and deletes no external functionality.
