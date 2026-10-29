# Proposal

## Why

Issue #2427: the scanner registry of `src/devops_cli/security/` holds a tflint adapter and a dive adapter, but `tools.lock` pins neither tool, and `devops install-tools` installs neither. `devops scan report` runs every scanner of the registry, so:

- **tflint.** The adapter sets `has_builtin_patterns`. With no tflint on PATH, each scan ran the hand-written check `_run_native_fallback_tf_lint`, which read each `.tf` file line by line for `0.0.0.0/0`. The scan status was `built-in patterns`, and `devops tf lint` and the agent tool `tf_lint` said the target was clean when the fallback found nothing.
- **dive.** The adapter has no fallback, so each scan with no dive on PATH was `unavailable`.

The fix of #2214 made the same decision for kubeconform (pinned, fallback deleted) and Checkov (adapter deleted). It left tflint and dive to this issue.

## What Changes

- **tflint is pinned.** `tools.lock` pins tflint 0.65.0 with a SHA-256 for each of `linux-amd64`, `linux-arm64`, `darwin-amd64` and `darwin-arm64`. tflint publishes `.zip` archives only, so `tools.lock` gets a fourth archive format, `zip`, which the installer unpacks with the standard library `zipfile`. A zip build names its member, as a tar.gz build does.
- **The tflint fallback goes.** `_run_native_fallback_tf_lint`, `_inspect_tf_file_fallback`, `_TfBlockContext`, `_is_security_context_line`, `_build_unrestricted_cidr_finding`, `fallback_scan` and `has_builtin_patterns` are deleted. With no tflint on PATH, the scan is `unavailable` with no finding. The check for `0.0.0.0/0` in IaC files is the job of `trivy-config`, which the registry holds (#2214).
- **`devops tf lint` and `tf_lint` report a lint that did not run.** Before, both read an empty result as a pass, whatever the status of the scan. `devops tf lint` now says that the lint did not run, with the status and the reason, and exits 1, as `devops k8s validate` does. The agent tool `tf_lint` runs the adapter through `_run_adapter_scan` and replies as the other agent scan tools reply.
- **The parser is checked against the tflint source.** The change reads the JSON shape, the exit codes and the severity names from the tflint source at `v0.65.0` (Feasibility). The parser already reads them correctly, so it does not change, and its tests use reports in that shape. No run of tflint is recorded yet: see "Pending a person" in the tasks.
- **dive goes.** The change deletes the dive adapter and every consumer of it. **This removes the command `devops docker analyze-layers` and the agent tool `docker_analyze_layers`.** It also deletes the constants `DEFAULT_DIVE_MIN_EFFICIENCY` and `DEFAULT_DIVE_MAX_WASTED_BYTES`, the knowledge base page of dive, and the help, message and model strings that only dive used. The registry holds 13 scanners. No shim stays: there is no other layer analysis, and `devops docker` has no command in its place. The reason is in Feasibility: dive has had no commit on its default branch for 17 months, and its newest release has 39 findings of HIGH or CRITICAL severity.
- **A test holds each scanner of the registry to a pinned program.** Every scanner of the registry names a program that `tools.lock` pins, or zizmor, which `pyproject.toml` pins as a dev dependency. Thus a scanner for an unpinned tool cannot enter the registry again.
- The commands, the agent tools, the registry and the lock are observable behavior, so the change has a spec delta:
  - ADDED requirements of `scanner-adapters` and `agent-scan-tools`.
  - The new capabilities `tf-lint` and `tflint-release-pin`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `tf-lint`: `devops tf lint` reports a lint that did not run as not run.
- `tflint-release-pin`: the tools lock pins tflint, and the installer unpacks a zip build.

### Modified Capabilities

- `scanner-adapters`: the tflint adapter reads the report that tflint writes and keeps no built-in patterns, every scanner of the registry has a pinned program, and the registry holds no dive adapter.
- `agent-scan-tools`: `tf_lint` runs the tflint adapter, and no tool analyzes image layers.

## Impact

- `src/devops_cli/tools_lock/__init__.py`, `src/devops_cli/tools_lock/tools.lock`, `src/devops_cli/commands/install_tools.py`.
- `src/devops_cli/security/tflint.py`, `src/devops_cli/security/registry.py`, `src/devops_cli/security/__init__.py`. `src/devops_cli/security/dive.py` is deleted.
- `src/devops_cli/commands/tf.py`, `src/devops_cli/commands/docker.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/tools/registry.py`, `src/devops_cli/ai/tools/__init__.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/models/docker.py`, `src/devops_cli/models/__init__.py`.
- The knowledge base pages `it_domains/tools/tflint.md` and `it_domains/tools/dive.md` (deleted), the knowledge base index, and the generated command and knowledge base documents.
- `tests/fixtures/swallowed_failures_ceilings.json`.
- `tests/security/test_tflint.py`, `tests/test_scanner_contract.py`, `tests/test_tools_lock.py`, `tests/test_install_tools.py`, `tests/test_tf.py`, `tests/test_builtin_tools.py`, and the tests of the registry, the docker commands and the agent tools. `tests/test_security_dive.py` is deleted.

## Feasibility

Each premise was checked on 2026-10-29. No downloaded program was run: the owner has not approved it, so the checks of tool output read the upstream source.

- **The tools are not pinned.** `tools.lock` on `origin/main` has no `tflint` and no `dive` entry, and `command -v` finds neither in the devcontainer.
- **tflint release.** `terraform-linters/tflint` has the release `v0.65.0` (2026-10-22), and six releases between 2026-04-19 and 2026-10-22. The licence is MPL-2.0, the repository is not archived, and its last push was 2026-10-28. Each asset has a `digest`. The assets are `tflint_<os>_<arch>.zip` and no other archive, and the zip of `linux-amd64` holds one file, `tflint`, with mode 0755. The `sha256` of each of the four platforms is the asset `digest`, and each equals its line in the release file `checksums.txt`. The `sha256sum` of the downloaded `tflint_linux_amd64.zip` is the same value. The release also has `checksums.txt.keyless.sig` and `checksums.txt.pem` (a cosign keyless signature). `cosign` is not installed in the devcontainer, so the signature was not verified. The digest, the checksum file and the downloaded bytes agree.
- **tflint output, read from the source at `v0.65.0`.** The adapter relies on these facts:
  - `formatter/json.go`: with `--format json`, tflint writes one object, `{"issues": [...], "errors": [...]}`, to stdout. Each issue has `rule` (`name`, `severity`, `link`), `message`, `range` (`filename`, `start`, `end`, each with `line` and `column`), `callers`, `fixable` and `fixed`. `issues` is never null. An error has `severity`, `message`, and optionally `summary` and `range`.
  - `formatter/formatter.go`, `toSeverity`: the severities of an issue are `error`, `warning` and `info`. The notice level of tflint is written as `info`. The existing mapping of `ERROR`, `WARNING` and `INFO` to HIGH, MEDIUM and LOW holds, and the parser upper-cases the name.
  - `cmd/cli.go`: the exit code is 0 (`ExitCodeOK`), 1 (`ExitCodeError`) or 2 (`ExitCodeIssuesFound`). `cmd/inspect.go`: tflint exits 2 when it found an issue and `--force` is not set, and exits 1 after it prints an error with no issue. The scanner base reads exit 2 with issues as a scan that ran, and exit 1 with no issue as a failed scan.
  - `cmd/cli.go`: tflint refuses a positional argument since v0.47 (`Command line arguments support was dropped in v0.47`). The adapter gives none and starts tflint in the directory of the target, as the base scanner does for each scan.
  - `cmd/option.go`: `--config` names the config file, and `--recursive` is off by default. So tflint reads the `.tf` files of the starting directory only. The adapter does not add `--recursive` in this change: the worker mode of tflint starts itself as a child process, and no run is at hand to check its output. A follow-up is named in the tasks.
- **No pinned tool covers tflint.** tflint lints the Terraform language and, with a plugin, the provider rules of a cloud. Trivy's misconfiguration scan (`trivy config`, pinned) is a security policy scan. So tflint is pinned, and it is not replaced. The check for `0.0.0.0/0` that the deleted fallback made is no tflint rule: it is a security policy, and `trivy-config` covers it.
- **dive release and state.** `wagoodman/dive` has the release `v0.13.1` (2025-03-29) as its newest release, and the releases before it are `v0.13.0` (2025-03-21), then 2024-02-02, 2023-07-07 and 2021-03-07. The newest commit on its default branch, `main`, is 2025-05-16 (a dependency bump), 17 months before this change. The licence is MIT. Its assets have no `digest`, and its only checksum file is `dive_0.13.1_checksums.txt`. The `sha256sum` of `dive_0.13.1_linux_amd64.tar.gz` equals its line there.
- **dive 0.13.1 carries known vulnerabilities.** `trivy rootfs --scanners vuln --severity HIGH,CRITICAL` (Trivy 0.75.0, a fresh database) over the extracted dive binary reported 39 findings, 38 HIGH and 1 CRITICAL. The Go standard library v1.24.1 has 27 of them, `golang.org/x/net` v0.37.0 has 6, `github.com/docker/docker` v28.0.4 has 2, `golang.org/x/text` v0.23.0 has 2, and `github.com/docker/cli` v28.0.2 and `github.com/klauspost/compress` v1.18.0 have 1 each. A pin would put these in `tools.lock`, and dive runs against the container engine of the person that runs it. The upstream has made no release that fixes them.
- **No pinned tool covers dive.** Trivy scans an image for vulnerabilities, secrets and misconfigurations, and it does not measure the wasted space of layers. The owner decided on 2026-10-29 to delete the adapter and its consumers.
- **The consumers of dive.** `grep` over `src/`, `tests/`, `docs/` and `README.md` finds dive in `security/dive.py`, `commands/docker.py` (`analyze-layers`), `ai/tools/builtin_tools.py` (`docker_analyze_layers`), `ai/tools/registry.py`, `ai/tools/__init__.py`, `config/defaults.py`, `lang/en/help.py`, `lang/en/messages.py`, `models/docker.py`, the knowledge base, and their tests. No OpenSpec capability names dive.
- **A missing tflint read as a pass.** `devops tf lint` and `tf_lint` treated an empty result as clean for each status, and `run_tflint_scan` returns the `ScanOutcome` of the scan. With the fallback gone, a missing tflint would read as a pass: the same defect that #2214 fixed for `devops k8s validate`. So the change fixes both callers.

## Existing Tool Considered

tflint (https://github.com/terraform-linters/tflint), now pinned, lints the Terraform files. Trivy (https://github.com/aquasecurity/trivy), pinned, scans them for misconfigurations. dive (https://github.com/wagoodman/dive) was considered and rejected for the reasons in Feasibility. The zip format uses the standard library `zipfile`. The change builds no scanner and no check.

The change deletes these hand-written checks and the code around them:

- `_run_native_fallback_tf_lint`, `_inspect_tf_file_fallback`, `_TfBlockContext`, `_is_security_context_line` and `_build_unrestricted_cidr_finding` in `tflint.py`.
- All of `dive.py`, the command `devops docker analyze-layers`, the agent tool `docker_analyze_layers`, and the constants, strings and models that only they read.
- The tests that held the fallback and dive.
