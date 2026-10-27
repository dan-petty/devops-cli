# Design

## Context

See proposal.md for background. `devops_cli.security.base.ScanOutcome` is a `list[Finding]` subclass with `status` and `reason`. `run_kubelinter_scan` returns it. `k8s_lint` calls it, prints the findings or a pass line, and returns, so it always exits 0.

## Goals / Non-Goals

**Goals:**
- Make the exit code of `devops k8s lint` the gate: 0 only on a clean run.
- Say, on an error line, when Kube-linter did not run, without a success line.

**Non-Goals:**
- Change the Kube-linter scanner or its adapter.
- Add a flag to force a pass.

## Decisions

### 1. Branch on the scan status, not on the findings count
- Decision: `k8s_lint` reads `findings.status` and, when it is not `ran`, prints an error and exits 1.
- Rationale: A missing binary and a failed run both return no findings, so the findings count alone cannot tell a clean run from a scan that did not run. The status names the outcome.
- Alternative considered: Check the return type or a separate `available` flag.
  - Rejected: `run_kubelinter_scan` already returns the status in `ScanOutcome`; a separate flag repeats it.

### 2. Exit 1 when Kube-linter ran and found findings
- Decision: `k8s_lint` exits 1 after printing the findings table.
- Rationale: A manifest Kube-linter flags is a lint failure the gate must read as non-zero.
- Alternative considered: Exit 0 and leave the gating to the CI pipeline.
  - Rejected: The command is the gate a pipeline keys on; a silent 0 reads a failure as a pass.

### 3. One error line for a scan that did not run
- Decision: Print `kube_linter_not_run` with the status and reason, then exit 1.
- Rationale: A reader of the line learns the outcome and the reason, and sees no success line.
- Alternative considered: Print no line and only set the exit code.
  - Rejected: A non-zero exit with no text leaves a reader guessing the reason.

## Risks / Trade-offs

- [A test or a caller passes a plain list, not a ScanOutcome] -> `k8s_lint` reads `findings.status`; the tests return a `ScanOutcome`, the type `run_kubelinter_scan` returns.
- [A non-ran status a reader does not expect] -> The line names the status and the reason, so the reader sees the outcome.
