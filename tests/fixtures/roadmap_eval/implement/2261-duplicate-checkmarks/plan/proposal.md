# Proposal

## Why

Issue #2261: `print_success` adds the success prefix `✓ ` to each message, but callers also start their messages with `✓ `, which causes the terminal to show the check mark two times.
For example, `devops gh metrics --emit-telemetry` prints `✓ ✓ Emitted project velocity metrics over OpenTelemetry to Prometheus.` on completion.

## What Changes

- Remove redundant `✓ ` and `✓` prefixes from message strings passed to `print_success` across the codebase.
- Remove redundant level prefix prefixes from message strings passed to other leveled print functions (`print_error`, `print_warning`, `print_info`, `print_step`).
- Add an AST invariant test in `tests/test_output.py` that parses every Python file in `src/devops_cli` and fails if any leveled print call begins with the prefix of its level.
- Update documentation examples in `src/devops_cli/ai/knowledge_base/devops_cli/libraries/rich.md` that demonstrated manual prefix inclusion.
- The change alters emitted command output messages that users observe. It fits in one pull request.

## Capabilities

### New Capabilities

- `console-output`: Provides formatted and leveled console output for the command-line interface, including level prefixes, styling, and stream routing.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/ai.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/commands/config.py`, `src/devops_cli/commands/docker.py`, `src/devops_cli/commands/gh.py`, `src/devops_cli/commands/k8s/networking.py`, `src/devops_cli/commands/k8s/security_audit.py`, `src/devops_cli/commands/scan.py`, `src/devops_cli/commands/test_cmd.py`, `src/devops_cli/commands/tf.py`, `src/devops_cli/commands/vault.py`.
- Documentation: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/rich.md`.
- Tests: `tests/test_output.py`.

## Feasibility

- The premise was confirmed against the live system. Executing `devops gh metrics --emit-telemetry` output `✓ ✓ Emitted project velocity metrics over OpenTelemetry to Prometheus.` on the final line.
- An AST scan of `src/devops_cli` confirmed that 25 calls to `print_success` in `src/devops_cli/commands/` start their message with `✓ ` or `✓`.
- The `parsed_source_trees` test fixture provides cached AST trees for all Python files under `src/devops_cli`, which enables fast AST validation without subprocess overhead.

## Existing Tool Considered

Python's standard library `ast` module and `pytest` are used to enforce this invariant across the repository.
No external library is required.
The change deletes manual prefix prefixes from 25 call sites and removes redundant manual prefix workarounds.
