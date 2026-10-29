# Design

## tflint is pinned as a zip build

`tools.lock` pins tflint 0.65.0 as a `zip` binary with the member `tflint`, for `linux-amd64`, `linux-arm64`, `darwin-amd64` and `darwin-arm64`. Each `sha256` is the asset `digest` of the release, checked against the release file `checksums.txt`. The lock needs no new note for the digest, but it gets one line for the zip format and the cosign signature, which `devops` does not verify.

- tflint publishes `.zip` archives only. The archive format `zip` joins `binary`, `gzip` and `tar.gz`. The installer reads the member with `zipfile.ZipFile` over the verified bytes, as it reads a tar.gz member with `tarfile`. It copies the member to the new file and sets the execute bit.
- A zip build names its member, as a tar.gz build does. The lock test that holds each tar.gz build to a member holds each zip build to one.

Rejected: the Docker image or `go install` of tflint. Each skips the pin, as the notes of `tools.lock` say for other tools.

Rejected: delete the tflint adapter. No pinned tool lints the Terraform language, and tflint is maintained, signed and under an open licence. The hand-written check was never tflint's: `0.0.0.0/0` is a security policy, and `trivy-config` covers it.

## The tflint fallback goes, and a scan that did not run is not a pass

The adapter keeps no `fallback_scan` and no `has_builtin_patterns`. With no tflint on PATH, the base scanner returns `unavailable` with the reason `Binary 'tflint' not found on PATH`. The two callers read an empty result as clean, whatever the status, so each changes with the fallback:

- `devops tf lint` says `TFLint lint <status>: <reason>. tflint linted no file, so the check did not pass.` and exits 1 when the status is not `ran`, before it prints in any format. It is the message and the exit of `devops k8s validate`.
- `tf_lint` runs `run_tflint_scan` through `_run_adapter_scan`, so the reply gives the status first and says that a scan with no result does not make the target clean. The target must be a path inside the workspace, as for the other scan tools.

## The parser reads the report that tflint writes

The facts and where they were read are in the proposal's Feasibility. The parser keeps its mapping: `error` is HIGH, `warning` is MEDIUM and `info` is LOW, each upper-cased. The scanner base already treats exit 2 with issues as a scan that ran, and exit 1 with no issue as a failed scan, so the adapter needs no code for the exit codes. The tests give the adapter reports in the shape of `formatter/json.go`, with lower-case severities. The earlier tests gave upper-case severities, which tflint does not write.

The command is `tflint --format json --recursive`. Without `--recursive`, tflint lints the `.tf` files of its starting directory only, so a target with `.tf` files in sub-directories only, such as `tf/` of a repository, would lint no file and read as clean. The deleted fallback read each `.tf` file below the target, so `--recursive` keeps that reach. The flag comes from the upstream source (`cmd/option.go`, `cmd/cli.go`, `cmd/inspect_parallel.go`; see Feasibility). The report has the same shape with it. The adapter starts tflint once and reads one report. The real run is still unrecorded, and it must confirm that a file name in a recursive report reads `<directory>/<file>`.

## dive goes

dive has had no commit on its default branch for 17 months, and the newest release carries 39 findings of HIGH or CRITICAL severity (Feasibility). No pinned tool covers it. So the change deletes the adapter and each consumer: the command `devops docker analyze-layers`, the agent tool `docker_analyze_layers`, the constants `DEFAULT_DIVE_*`, the help and message strings, the models `DiveRequest` and `DiveResult` of `models/docker.py` if nothing else reads them, and the knowledge base page. No shim stays, because devops-cli is alpha software.

Rejected: pin dive 0.13.1. The lock would hold a binary with 39 HIGH or CRITICAL findings and no fix upstream, and the project takes no unmaintained dependency.

Rejected: keep the adapter and say that dive is not installed. A scanner that no pin can supply is `unavailable` on each scan, which is the state that the issue reports.

## Each scanner of the registry has a pinned program

A test reads `binary_name` of each scanner of the default registry and requires it in `tools.lock` (a command of some tool) or in the dev dependencies of `pyproject.toml`. zizmor is the one scanner with a dev pin. So a scanner for an unpinned tool fails the test when it enters the registry.

## Out of scope

- A run of tflint recorded in `tests/fixtures/scanner_runs/runs_with_findings.json`, with its version held to `tools.lock` by `test_each_run_with_findings_is_of_the_version_the_tools_lock_pins`. It needs a run of the downloaded tflint, which the owner has not approved. A person records it so:
  1. In a scratch directory `<scratch>`, set `HOME=<scratch>/home` and run `uv run devops install-tools --tool tflint --target-dir <scratch>/bin`. The installer checks the build against the `sha256` of the lock. `<scratch>/bin/tflint --version` must print `0.65.0`.
  2. In `<scratch>/tree`, write a `main.tf` with `variable "unused" {}`. From `<scratch>/tree`, run `<scratch>/bin/tflint --format json --recursive`, which is the command of the adapter. Write a second `.tf` file in `<scratch>/tree/modules/network` and keep the file names that the report gives for it. Keep its exit code, stdout and stderr. The exit code must be 2, and the report must hold one issue or more. Where the report has none, add a `.tf` line that the bundled `terraform` ruleset flags, such as `x = "${var.a}"`.
  3. Add the key `tflint` to `runs_with_findings.json` with `version` `0.65.0`, `argv` `["tflint", "--format", "json", "--recursive"]`, `cwd` `{tree}`, `returncode`, `stdout` and `stderr`, with the path of `<scratch>/tree` replaced by `{tree}`.
  4. Add a test to `tests/security/test_tflint.py` that scripts the run with `scanner_fake.script_run_with_findings("tflint", tree=tmp_path)` and asserts the findings that `run_tflint_scan` gives. `test_each_run_with_findings_is_of_the_version_the_tools_lock_pins` then holds the recording to the locked version.
