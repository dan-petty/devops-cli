# Design

## kubeconform is pinned as a binary

`tools.lock` pins kubeconform 0.8.0 as a `tar.gz` binary with the member `kubeconform`, as it pins Pluto and Trivy. Each `sha256` is the asset `digest` of the release, checked against the release file `CHECKSUMS`. The lock needs no new note: the release has a digest for each asset.

Rejected: the check `schema-validation` of kube-linter, which `tools.lock` pins. It runs kubeconform as a library, but only over objects that kube-linter decodes into their Go types. A Service with `port: "http"` does not decode, so the check did not report it. The only report of it came from `--fail-on-invalid-resource`, a flag that kube-linter 0.8.3 marks as deprecated. The check also skips a resource with no schema, and it is not in the default checks.

## The parser reads one report object

`kubeconform -output json` writes one JSON object, `{"resources": [...]}`. The parser gives one HIGH finding for each resource with `statusInvalid` or `statusError`, in the order of the report. It gives no finding for `statusValid` or `statusSkipped`. It reads `filename`, `kind`, `name` and `status` without a default, as the Pluto parser does (#1434). A report that lacks one of them raises, and the base scanner reports a failed scan.

- The location is `<manifest>:<Kind>/<name>`, as Pluto names its findings. `manifest_location` of the kube-linter adapter names the manifest, and `manifest_object_key` names the object. kubeconform writes no namespace and no line. A resource that kubeconform could not read has an empty `kind`. A file that is not YAML is an example. The location of such a resource is the manifest alone.
- The title names the status and the object: `[Kubeconform statusInvalid] Service 'web' does not match its schema`, or `[Kubeconform statusError] ...` with `could not be validated`. The description is `msg`. The fix of an invalid resource names each `path` and `msg` of `validationErrors`.

Rejected: the location `<manifest>:1` of the old parser. Two invalid resources of one file then have one location, and the review merges findings by location.

Rejected: `-ignore-missing-schemas`. A custom resource with no schema was not validated. The finding says so, and the person can name a schema location for it. The issue asks for one HIGH finding for each `statusError` resource.

Rejected: `-verbose` in the command. It adds the valid and skipped resources to the report, and the parser drops them. The `-verbose` recording proves that the parser drops them.

## kubeconform gets the manifests alone

kubeconform reads each `.yaml`, `.yml` and `.json` file of a directory that it gets. It reports each file that is not a manifest as `statusError`, with `missing 'kind' key`, `missing 'apiVersion' key` or a YAML error. Over `k8s/` of this repository, it gave 33 such resources: the Helm values files, `k8s/llm/gateway/config.yaml` and the Grafana dashboards. The parser makes each of them a HIGH finding.

- The adapter gives kubeconform the path of each manifest of the target, and not the target.
- A manifest is a file that `is_kubernetes_manifest` accepts: a YAML or JSON file with a document that has `apiVersion`. The review chooses the manifests for kube-linter and Pluto with the same function.
- The adapter reads only the files that git lists and does not ignore (`list_repo_files`), as the deleted fallback did. Thus kubeconform reads no virtual environment and no data directory.
- A target with no manifest is `not_applicable`, and kubeconform does not start. `devops k8s validate` then says why, and exits 1.

Rejected: `-ignore-filename-pattern`. A file name does not tell a Helm values file from a manifest.

## No schema fetch step

kubeconform reads each schema from `raw.githubusercontent.com` unless `-schema-location` names another place. A review runs its tools in a sandbox with no network (#2096), but no review runs kubeconform: the review scans manifests with kube-linter and Pluto. `devops k8s validate`, `devops scan report` and the agent tool start kubeconform on `DirectToolExecutor`, which has the network. So the change adds no fetch step and no data directory. A change that makes a review run kubeconform adds them, as osv-scanner and Trivy have them.

## No fallback for a pinned tool

The kubeconform adapter has no `fallback_scan` and keeps `has_builtin_patterns` False. With no binary, the scan is `unavailable` with the reason `Binary 'kubeconform' not found on PATH`. `devops k8s validate` says that the validation did not run and exits 1, as `devops k8s lint` does. Before, the command said that every manifest was valid when the tool did not run and the fallback found nothing. The agent tool `k8s_validate_manifests` replies through `_scan_reply`. Its reply gives the status first, and says that a scan with no result does not make the target clean.

## Checkov goes, and Trivy's misconfiguration scan takes its place

The evidence is in the proposal's Feasibility: Trivy, which is pinned, has a check for each defect that Checkov found on the same files. Checkov wrote no severity without an API key, and it reached `pypi.org` and `api0.prismacloud.io` on each run.

- `devops scan iac` goes. `devops scan trivy --type config <target>` scans IaC files, and the MCP tool `scan_trivy` takes the same `scan_type`.
- The registry holds `TrivyConfigScanner`, named `trivy-config`, in the place of `CheckovScanner`. It is the Trivy adapter with `config` as its default scan type, so `devops scan report` runs `trivy config` over the target beside `trivy fs`. The registry still holds 14 scanners.
- The static job of CI installs the pinned Trivy before its security scan. Before, the Checkov fallback was the IaC check of that scan, and its findings went to code scanning. Now `trivy-config` checks the IaC files there. Over this tree it found the privileged container and the root user that the Checkov fallback found, and 46 more findings, in 23 s. The scan skips `trivy`, the filesystem scan, which took 194 s over this tree. The audit row of the quality gate checks the dependencies.
- The agent tool `scan_iac` runs `run_trivy_scan` with the scan type `config`, and replies as `scan_trivy` does.

Rejected: pin Checkov as a Python tool and read `severity`, with a fixed level for `null`. Each Checkov finding then has the same level, because Checkov writes `null` for each check without an API key. The pin adds 97 packages and a recording for each of about two releases a week. A run without phone-home also needs `--skip-download`, which drops the guideline links, and an environment variable that the scanner base cannot pass to a tool.

Rejected: keep `devops scan iac` and make it run Trivy. The command then repeats `devops scan trivy --type config`. devops-cli keeps no second path to one function.

Rejected: add `misconfig` to the scanners of `trivy fs`. `devops scan trivy` and the dependency remediator run `trivy fs`, and the remediator reads each of its findings as a vulnerability.

## Out of scope

- `devops k8s validate` shows the findings of kubeconform and exits 0, as `devops k8s check-deprecated` does for Pluto. The change makes only a validation that did not run fail the command, because the deleted fallback made it a pass. A finding that fails the command is a separate decision for `devops k8s validate`, `check-deprecated` and `audit` together.
- `tflint` and `dive` are in the registry and not in `tools.lock`, and the tflint adapter keeps its hand-written fallback. The issue names kubeconform and Checkov only, and #2427 decides tflint and dive.
