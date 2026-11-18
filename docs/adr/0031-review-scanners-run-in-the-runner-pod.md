---
status: proposed
date: 2026-11-21
decision-makers: [owner]
issue: 3827
---

# Review scanners run in the runner pod

## Context and Problem Statement

`devops review` starts each scanner in a `bubblewrap` sandbox (ADR 0005). The sandbox needs a user namespace, and a user namespace needs `unshare`. The `RuntimeDefault` seccomp profile of a runner pod refuses `unshare` (`src/devops_cli/core/process_hardening.py`). So a review cannot run in the shell of a runner Job.

The runner table `NOT_IN_RUNNER` named Gitleaks, Pluto, golangci-lint and Semgrep, as scanners that no step of a Job counts on. A review in the runner found nothing, and a scanner that is not installed read as no finding.

## Considered Options

- **The direct executor in the pod of the runner Job**: `DirectToolExecutor` starts each scanner with no sandbox. The pod is the isolation boundary: it holds no Kubernetes token, the step shell holds none of the job variables, and the job process is not dumpable. Chosen.
- **`bubblewrap` in the pod**: the pod refuses the `unshare` that the sandbox needs. Rejected.
- **A rootless container runtime in the pod**: the Job has no container engine, and `docker` is in `NOT_IN_RUNNER` for that reason. Rejected.
- **A second pod for the scanners**: the Job has no cluster token, so it cannot start a pod. Rejected.

## Decision Outcome

Chosen option: "The direct executor in the pod of the runner Job", because the pod is already the isolation boundary and no other option can run in the pod.

- The review chooses its executor from the setting `roadmap.implement.in_runner`. Only the pod of a runner Job sets it. A workstation and the Service pod keep the sandbox.
- The runner image holds Gitleaks, Pluto, osv-scanner, golangci-lint and Semgrep, which its base, the devtools image, installs. The `Dockerfile` of this project pins no scanner. Each one is an entry of `RUNNER_TOOLS` with the source `ToolSource.DEVTOOLS`, and the smoke test of the image runs its version command.
- A review in the runner pod fails closed when an analyzer that its files need is not installed. The report lists that scanner as not installed, and the command exits 1. A workstation review stays advisory.

## Consequences

- A review in the runner finds what the five scanners find, and a missing scanner is a broken image and not a clean review.
- The scanners come with a new devtools image, so a scanner version changes there and not in this project. The image scan of the runner stays report-only (`docs/CLUSTER.md`).
- Isolation of a scanner depends on the pod. A change to the pod that gives it a Kubernetes token or the job variables in the step shell must come with a new record.
- ADR 0005 stays as it is. This record is the one exception, and it applies only to the pod of a runner Job.
