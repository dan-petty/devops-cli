# Proposal

## Why

Issue #2095: `devops k8s lint` exits 0 in two cases where it must not. When Kube-linter is not on PATH, the command prints a success line and exits 0. When Kube-linter reports findings, the command prints the findings and exits 0. In both cases, a CI gate that keys on the exit code reads a failure as a pass.

## What Changes

- In `src/devops_cli/commands/k8s/security_audit.py`, `k8s_lint` reads the `ScanOutcome` the scanner returns and branches on its status.
- When the status is not `ran`, the command prints an error line that names the status and the reason, says the manifest was not audited, and exits 1. It prints no success line.
- When the status is `ran` with no findings, the command prints the pass line and exits 0.
- When the status is `ran` with findings, the command prints the findings table and exits 1.
- Add the `kube_linter_not_run` message to `K8sMessages` in `src/devops_cli/lang/en/messages.py`.
- Update `tests/test_k8s.py`: `test_k8s_lint_exit_codes` asserts the exit code and the message for a clean run, a run with findings, and an unavailable Kube-linter; `test_k8s_security_tools_and_scans` returns a `ScanOutcome` and expects exit 1 for findings.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `k8s-lint`: Audit a manifest or Helm chart with Kube-linter, report the findings, and make the exit code the gate: 0 only on a clean run.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/commands/k8s/security_audit.py`: `k8s_lint` branches on the scan status and exits 1 when Kube-linter did not run or found findings.
- `src/devops_cli/lang/en/messages.py`: adds `kube_linter_not_run`.
- `tests/test_k8s.py`: adds `test_k8s_lint_exit_codes` and updates `test_k8s_security_tools_and_scans`.

## Feasibility

- `devops_cli.security.base.ScanOutcome` is a `list[Finding]` subclass with `status` and `reason`; `devops_cli.security.kubelinter.run_kubelinter_scan` returns it, and `k8s_lint` already calls it.
- Confirmed against the source: `ScanOutcome("ran", [finding])` is truthy, `ScanOutcome("ran", [])` is empty, and `run_kubelinter_scan` sets `status` to `unavailable` when the binary is not on PATH.

## Existing Tool Considered

The command already calls Kube-linter through `devops_cli.security.kubelinter`; this change reads the status the scanner already returns and sets the exit code from it. No new tool or library is required, and the change deletes no internal code.
