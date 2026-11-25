### Problem Description

`print_success` (`src/devops_cli/output/console.py`) adds the success prefix `✓` to each message. 19 callers also start their message with `✓ `, so the person sees the check mark two times.

### Reproduction Steps

1. Run `devops gh metrics --emit-telemetry`.
2. Read the last line.

`grep -rn 'print_success(f\?"✓' src/devops_cli` finds the 19 callers, in `commands/gh.py`, `commands/vault.py`, `commands/scan.py`, `commands/docker.py` and others.

### Expected vs Actual Behavior

- Expected: `✓ Emitted project velocity metrics over OpenTelemetry to Prometheus.`
- Actual: `✓ ✓ Emitted project velocity metrics over OpenTelemetry to Prometheus.`

### Environment Diagnostics

`main` at 990e4d1f.

### Proposed remedy

Remove `✓ ` from the 19 messages. Add a test that fails when a message given to `print_success`, `print_error`, `print_warning` or `print_info` starts with the prefix of its level.

### Acceptance criteria

- [ ] No message given to a `print_*` function starts with the prefix that the function adds.
- [ ] A test reads every call in `src/devops_cli` and fails on such a message.


Source: https://github.com/dan-petty/devops-cli/issues/974
