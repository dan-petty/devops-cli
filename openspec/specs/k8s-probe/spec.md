# k8s-probe Specification

## Purpose
The `probe` subcommand of the `k8s` group measures what a labeled throwaway pod reaches over HTTP, so an operator proves a network policy path without a hand-made pod.

## Requirements

### Requirement: One labeled probe pod
The command SHALL create exactly one pod in the given namespace with the given label, and SHALL send each HTTP attempt with `kubectl exec` into that pod.

#### Scenario: One pod for the whole probe
- **WHEN** The operator runs the `probe` subcommand of the `k8s` group with `--namespace devops`, `--label app.kubernetes.io/name=devops-cli-job` and `--url http://<mcp-service>:8001/implementation/mcp`, with the process fake.
- **THEN** The fake records one `kubectl run` call that carries the namespace devops and the label app.kubernetes.io/name=devops-cli-job, and no second run call.

### Requirement: Restricted security context
The probe pod MUST set the security context of the shared throwaway pod, so that it passes the Pod Security restricted level.

#### Scenario: Pod spec passes restricted Pod Security
- **WHEN** The command builds the pod spec.
- **THEN** The spec sets `runAsNonRoot: true`, a non-zero `runAsUser`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile.type: RuntimeDefault`, `readOnlyRootFilesystem: true` and `automountServiceAccountToken: false`.

### Requirement: Wait for the policy
The command MUST retry the request while the pod's `curl` exits 7, until the `--wait` deadline, and SHALL take the first attempt that does not exit 7 as its measurement.

#### Scenario: A refused connection is retried
- **WHEN** The process fake answers the first two exec calls with exit code 7 and the third with standard output 401.
- **THEN** The command makes three exec calls and prints `status=401`.

### Requirement: Blocked result
The command SHALL print the `curl` exit code and exit 0 when the `--wait` deadline passes with `curl` exit 7 and no HTTP response, because a blocked path is a measurement.

#### Scenario: A blocked path prints the exit code
- **WHEN** The process fake answers every exec call with exit code 7 until the wait deadline of 20 seconds.
- **THEN** The command prints `curl_exit=7` and exits 0.

### Requirement: Probe deadline
The command MUST stop the probe and report a timeout with a non-zero exit when the overall `--timeout` deadline passes before the measurement.

#### Scenario: Deadline stops a slow probe
- **WHEN** The operator runs the subcommand with `--timeout 5` and `--wait 20`, and the process fake answers each exec call with exit code 7 so that the clock passes the timeout deadline.
- **THEN** The command prints a timeout message, records the pod deletion and exits non-zero.

### Requirement: Credential off the command line
The command MUST send each header value to `curl` on standard input, and MUST NOT hold it in any command line or in the output.

#### Scenario: A secret header stays off every argv and out of the output
- **WHEN** The operator passes `--header 'Authorization: Bearer s3cr3t'` and the process fake answers the measured request with status 200.
- **THEN** No recorded argv holds the header value, the standard input of the exec call holds it, and the standard output and the standard error hold it nowhere.

### Requirement: Pod deletion
The command MUST delete the probe pod before it exits, including after an error or a timeout.

#### Scenario: Pod deleted after a failed probe
- **WHEN** The process fake fails the first exec call with exit code 2 and no kubectl exit line.
- **THEN** The fake records one `delete pod --ignore-not-found` call for the generated pod name, and the command exits non-zero.

### Requirement: Dry run
The command SHALL create no pod and send no request with `--dry-run`, and SHALL print the pod call, the `curl` command line and the URL.

#### Scenario: Dry run prints the plan only
- **WHEN** The operator runs the subcommand with `--dry-run`.
- **THEN** The fake records no run, no exec and no delete call, and the output holds the `kubectl run` call, the `curl` command line and the URL.

### Requirement: Pinned image
The probe pod MUST use an image pinned by digest, and the command MUST refuse an `--image` value that holds no digest before any `kubectl` call.

#### Scenario: The image names a digest
- **WHEN** The command builds the pod spec with the default image and with `--image`.
- **THEN** Each image reference holds the digest marker `@sha256:`, and an `--image` value that holds no digest is refused before any kubectl call.
