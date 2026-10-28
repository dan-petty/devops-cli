# Proposal

## Why

Issue #2214: the scanner registry of `src/devops_cli/security/` holds a kubeconform adapter and a Checkov adapter, but `tools.lock` pins neither tool, and `devops install-tools` installs neither. Both adapters set `has_builtin_patterns`, so each scan ran hand-written checks in place of the tool: `_run_native_fallback_k8s_validation` in `kubeconform.py` and `_run_native_fallback_iac_checks` in `checkov.py`. When a person installed a tool by hand, the adapter read its output wrong:

- **kubeconform.** `_parse_kubeconform_line` read one JSON object for each line, with `status` `invalid` or `error`. `kubeconform -output json` writes one object, `{"resources": [...]}`, and each status is `statusValid`, `statusInvalid`, `statusError` or `statusSkipped`. Thus a report with invalid resources gave no finding.
- **Checkov.** `_parse_checkov_check` took the severity from the name of the check, so the `LOW` in `ALLOW` made a check LOW, and it did not read the `severity` field.

The issue asks for a decision: pin both tools and fix the parsers, or delete the adapters when pinned tools cover the same checks.

## What Changes

- **kubeconform is pinned.** `tools.lock` pins kubeconform 0.8.0 as a binary with a SHA-256 for each platform. No other pinned tool validates every resource against the Kubernetes JSON schemas (Feasibility).
- **The kubeconform parser reads the report that kubeconform writes.** Each resource with `statusInvalid` or `statusError` is one HIGH finding at `<manifest>:<Kind>/<name>`. A resource with `statusValid` or `statusSkipped` gives no finding.
- **The kubeconform fallback goes.** With no kubeconform on PATH, the scan is `unavailable` and has no findings. `devops k8s validate` then says that the validation did not run and exits 1, as `devops k8s lint` does for kube-linter. The agent tool `k8s_validate_manifests` runs the adapter and replies as the other agent scan tools reply, so a validation that did not run never reads as a pass.
- **Checkov goes.** The pinned Trivy scans the same IaC files with its misconfiguration checks, and Checkov adds no signal that Trivy does not give (Feasibility). The change deletes the Checkov adapter, its hand-written checks, the constants that only those checks read, and `devops scan iac` with its MCP tool. `devops scan trivy --type config` is the IaC scan of the command line.
- **Trivy's misconfiguration scan takes the place of Checkov in the registry.** The registry holds `trivy-config`, which runs `trivy config` over the target, so `devops scan report` still scans IaC files. The agent tool `scan_iac` runs Trivy's misconfiguration scan.
- **The recordings.** `tests/fixtures/scanner_runs/runs_with_findings.json` holds a run of kubeconform 0.8.0 with the command of the adapter. `tests/fixtures/scanner_runs/kubeconform_verbose_run.json` holds a `-verbose` run with all four statuses. A contract test holds each run with findings to the version that `tools.lock` pins.
- The commands, their output, the registry and the agent tools are observable behavior, so the change has a spec delta: ADDED requirements of `scanner-adapters` and `agent-scan-tools`, the requirement of `scan-json-stdout` MODIFIED to name no `scan iac`, and the new capability `k8s-validate`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `k8s-validate`: `devops k8s validate` reports a validation that did not run as not run.

### Modified Capabilities

- `scanner-adapters`: the kubeconform adapter, the registry entry of Trivy's misconfiguration scan, and no hand-written fallback for kubeconform.
- `agent-scan-tools`: `k8s_validate_manifests` and `scan_iac` run the pinned adapters.
- `scan-json-stdout`: the JSON stdout requirement names no `devops scan iac`, which the change deletes.

## Impact

- `src/devops_cli/tools_lock/tools.lock`.
- `src/devops_cli/security/kubeconform.py`, `src/devops_cli/security/trivy.py`, `src/devops_cli/security/registry.py`, `src/devops_cli/security/__init__.py`. `src/devops_cli/security/checkov.py` is deleted.
- `src/devops_cli/commands/scan.py`, `src/devops_cli/commands/k8s/security_audit.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/kb.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/models/security.py`.
- The knowledge base pages `it_domains/tools/kubeconform.md`, `it_domains/tools/trivy.md`, `devops_cli/cli_command_reference.md` and `it_domains/tools/checkov.md` (deleted), the knowledge base index, `docs/DEVCONTAINER_USAGE.md`, `.github/labels.yml`, and the generated command, MCP and knowledge base documents.
- `tests/fixtures/scanner_runs/`, `tests/test_security_kubeconform.py`, `tests/test_scanner_contract.py`, and the tests of the registry, the scan commands, the k8s commands, the agent tools and the knowledge base. `tests/test_security_checkov.py` is deleted.

## Feasibility

Each premise was checked on 2026-10-28:

- **The tools are not pinned.** `tools.lock` on `origin/main` has no `kubeconform` and no `checkov` entry. `command -v` finds neither in the devcontainer.
- **kubeconform 0.8.0 output.** The release `v0.8.0` of yannh/kubeconform (2026-06-04) has an asset `digest` for each archive, and each digest matches its line in the release file `CHECKSUMS`. `devops install-tools --tool kubeconform` installed the pin from the new lock entry. `kubeconform -output json -kubernetes-version master -strict <dir>` over a manifest with a valid Deployment, a Service with `port: "http"`, a ConfigMap with an extra key and a custom resource wrote one object, `{"resources": [...]}`, with two `statusInvalid` resources and one `statusError` resource (`could not find schema for Widget`), and exited 1. Without `-verbose` it lists no valid resource. With `-verbose -skip ConfigMap` it also wrote `statusValid` and `statusSkipped`. A clean run wrote `{"resources": []}` and exited 0. Each resource has `filename`, `kind`, `name`, `version`, `status` and `msg`, and no line number.
- **No other pinned tool covers kubeconform.** kube-linter 0.8.3 has the check `schema-validation`, which uses kubeconform as a library, but it is not in the default checks. With `--include schema-validation` over the same manifest, kube-linter reported the ConfigMap and nothing about the Service, because an object that does not decode into its Go type does not reach the check. Its only report of that object is `failed-to-load-object`, from the flag `--fail-on-invalid-resource`, which kube-linter marks as deprecated. The check also skips a resource with no schema. Trivy's Kubernetes checks are security policies, not schema validation.
- **No review runs kubeconform.** The review scans manifests with kube-linter and Pluto (`_scan_kubernetes_manifests` in `src/devops_cli/ai/review/pipeline.py`), and imports only `is_kubernetes_manifest` from `kubeconform.py`. `devops k8s validate`, `devops scan report` and the agent tool start kubeconform on `DirectToolExecutor`, which has the network. So no sandboxed run of kubeconform exists, and the change adds no fetch step for its schemas. The issue asked for one on the premise that a review runs kubeconform in the sandbox of #2096. That premise is false.
- **Trivy covers the Checkov checks.** Checkov 3.3.30, installed from hashed requirements into a scratch environment on Python 3.14, and Trivy 0.75.0 (`trivy config`) scanned the same Dockerfile, Terraform security group and Pod. Each defect that Checkov found has a Trivy check: the base image on `latest` (CKV_DOCKER_7, DS-0001), no USER (CKV_DOCKER_3, DS-0002), no HEALTHCHECK (CKV_DOCKER_2, DS-0026), SSH open to `0.0.0.0/0` (CKV_AWS_24, AWS-0107), no description (CKV_AWS_23, AWS-0099), a privileged container (CKV_K8S_16, KSV-0017), privilege escalation (CKV_K8S_20, KSV-0001), the image tag `latest` (CKV_K8S_14, KSV-0013), no read-only root file system (CKV_K8S_22, KSV-0014), no CPU and memory limits and requests (CKV_K8S_10 to 13, KSV-0011, 0015, 0016, 0018), root and low UIDs (CKV_K8S_23 and 40, KSV-0012 and 0020), no seccomp profile (CKV_K8S_31, KSV-0030), the default namespace (CKV_K8S_21, KSV-0110) and capabilities (CKV_K8S_28 and 37, KSV-0003 and 0004). kube-linter 0.8.3 has `no-liveness-probe` and `no-readiness-probe` for CKV_K8S_8 and 9. `trivy config --help` lists the misconfiguration scanners `azure-arm`, `cloudformation`, `dockerfile`, `helm`, `kubernetes`, `terraform` and `ansible`. A review already scans container files with `trivy config`.
- **Checkov gives no severity.** Without a Prisma Cloud API key, Checkov 3.3.30 wrote `"severity": null` for each of its 26 failed checks. So the severity fix that the issue asks for gives each Checkov finding the same fixed level. Trivy writes a severity for each check.
- **Checkov reaches the network on each run.** Each run asks `pypi.org` for a newer version unless `CKV_SKIP_PACKAGE_UPDATE_CHECK` is set (`checkov/common/util/banner.py`), and asks `api0.prismacloud.io` for its guidelines unless `--skip-download` is given. Without the network, it logged `Failed to get the checkov mappings and guidelines` and went on. SECURITY.md item 9 asks for no phone-home.
- **The pin of Checkov costs more than it gives.** `uv pip compile --universal --generate-hashes --python-version 3.14` for `checkov==3.3.30` gives 97 packages in 2317 lines. PyPI lists 22 releases of Checkov from 2026-07-28 to 2026-10-28, and each bump needs a new recording. The classifiers of Checkov name Python 3.9 to 3.12, and `tools.lock` installs every Python tool on Python 3.14.

## Existing Tool Considered

kubeconform (https://github.com/yannh/kubeconform), now pinned, validates the manifests. Trivy (https://github.com/aquasecurity/trivy), which `tools.lock` pins, scans IaC files for misconfigurations in place of Checkov (https://github.com/bridgecrewio/checkov). kube-linter's `schema-validation` check was considered and rejected for the reasons in Feasibility. The change builds no scanner and no check.

The change deletes the hand-written checks: `_run_native_fallback_k8s_validation` and `_validate_single_k8s_file_fallback` in `kubeconform.py`, and all of `checkov.py`, with its Dockerfile instruction parser, its YAML walk for privileged containers and the 16 constants of `config/constants.py` that only they read. It also deletes `_parse_kubeconform_line`, `devops scan iac`, the knowledge base page of Checkov and the tests that fed the adapters reports in shapes that the tools do not write.
