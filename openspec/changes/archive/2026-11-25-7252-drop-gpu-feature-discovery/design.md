# Design

## Decisions
- Remove the DaemonSet from the native deploy, rather than repair it: nothing reads its output.

## Rejected alternatives
- Pin v0.16.2 again: it stays a privileged workload that does nothing, and each update offers v0.20.2 again.
- Add Node Feature Discovery and the `nvidia` runtime: a new component with no consumer that needs it.
