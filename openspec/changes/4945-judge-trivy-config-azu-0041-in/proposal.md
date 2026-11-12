# Proposal

## Why

Trivy-config reports AZU-0041 for tf/azure/main.tf at CRITICAL severity, and the AKS cluster of the module sets no network policy, so the cluster enforces no Kubernetes NetworkPolicy object; #4945 judges the alert by the first choice of SECURITY.md, a fix of the file, and the stack needs the policy engine to enforce its NetworkPolicy objects.

## What Changes

- Set network_policy to azure in the network profile of the AKS cluster in `tf/azure/main.tf`.
- Add `tests/invariants/test_azure_aks_network_policy.py`, which parses the Azure module with parse_hcl_directory and asserts the Azure policy engine beside the Azure CNI plugin.
- Document in `tf/README.md` the network policy engine of the AKS cluster, the devops tf init and devops tf validate commands, and the Trivy config scan of the module, whose result clears AZU-0041.
- Add the capability azure-aks-cluster to the spec delta, with two network policy requirements that the new invariant test asserts.
- Keep `SECURITY.md` as it is: the change takes its first choice, a fix of the file, and adds no ignore entry and no dismissal.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `azure-aks-cluster`: The AKS network profile sets a network policy, Azure CNI selects the Azure network policy engine

### Modified Capabilities

None.

## Impact

- Code: `tf/azure/main.tf`
- Documents: `tf/README.md`
- Tests: `tests/invariants/test_azure_aks_network_policy.py`

## Feasibility

- The probe line reads, word for word: The path `tf/azure/main.tf` is a file of the staging commit.
- The probe line reads, word for word: The path `SECURITY.md` is a file of the staging commit.
- The probe line reads, word for word: The path `azurerm_kubernetes_cluster.aks` is no file of the staging commit. No commit in the history deleted or renamed it. — that probe answers a path question about a resource address, so it shows no false premise: `tf/azure/main.tf:44:resource "azurerm_kubernetes_cluster" "aks" {` holds the resource.
- The probe line reads, word for word: The path `.trivyignore.yaml` is no file of the staging commit. No commit in the history deleted or renamed it. — the plan adds no ignore entry, so the absent file is no fault.
- The probe line reads, word for word: Not probed, the bound of 10 commands is reached: `network_profile`, `network_policy` — so this run confirms the two identifiers with read_file instead.
- read_file of `tf/azure/main.tf` lines 44 to 79 shows `tf/azure/main.tf:67:network_profile {` with `tf/azure/main.tf:68:network_plugin = "azure"` and no network policy argument in the block, so the control that AZU-0041 names is absent and the fix of the file is the premise of the item.
- read_file of `SECURITY.md` lines 78 to 92 shows `SECURITY.md:87:1. Fix the file in a pull request that closes the issue. This is the first choice.`, which makes the fix the first choice.
- `SECURITY.md:88:never for a CRITICAL alert, never for a secret.` refuses an ignore entry for this CRITICAL alert, and `SECURITY.md:89:3. A person dismisses the alert in code scanning, with a reason. An agent does not dismiss an alert.` keeps a dismissal to a person.
- The review finding is fixed: the plan no longer claims an excluded-tools entry for `tofu`. The image tools list of the runner capabilities holds `uv`, `python`, `pytest`, `ruff`, `mypy` and no `tofu`, and the excluded-tools list holds no `tofu` entry either, so `tofu` is absent from the runner by the absence of a binary in the image and not by a named exclusion.
- `docs/DEVCONTAINER_USAGE.md:38:the image ships neither` confirms that the project installs no `tofu` binary, so the OpenTofu commands of group 2 are a person's commands on a host that holds OpenTofu, and no pod setting applies to them.
- `trivy` is an excluded tool of the runner capabilities, `NOT_IN_RUNNER` with the entry that a Job cannot run the IaC scan of the Security Scan step, so no pod setting applies to the config scan that a person runs.
- The failure class of the two commands of group 2 is a non-zero exit of the OpenTofu or Trivy binary, which the person reads, and each command needs a checkout of the repository and a network for the provider registry or the rule cache; no runner capability is involved.
- The `criterion_dropped` finding is fixed at the group: group 2 runs the pinned Trivy's config scan over the module and records the result in `tf/README.md`, and group 1 changes the module data that the criterion needs.
- The delta states the condition that AZU-0041 requires and not a scanner run, because `docs/TESTING.md:76:No test starts a real security scanner either` refuses a test that starts a scanner, and the runner capabilities list trivy as NOT_IN_RUNNER; the scan itself is the process of group 2.
- The Security Scan step of the pull request runs the IaC scan: `.github/workflows/ci.yml:96:run: uv run devops scan report --sarif .data/scan.sarif --skip bandit,trivy` skips the `trivy` filesystem scanner and keeps `trivy-config`, so the pull request produces the AZU-0041 result that group 2 confirms is gone.
- One function that the plan calls needs a checkout: `parse_hcl_directory(directory)` of `src/devops_cli/tf/analysis.py` opens the HCL files of the checkout; it needs no client of a service and no network.
- `src/devops_cli/tf/analysis.py:189:def parse_hcl_directory(directory: Path) -> IaCConfiguration:` returns the resources with their attributes, and `src/devops_cli/tf/analysis.py:def _strip_block_markers` keeps a nested block as a list of dicts, so the new test reads the first entry of the network profile list.
- `tests/support/paths.py:21:REPO_ROOT: Final[Path] = TESTS_ROOT.parent` gives the repository root to the new test, so the test counts no parent folder.
- The verify of group 1 is `uv run devops ci test tests/invariants/test_azure_aks_network_policy.py`: pytest is an image tool of the runner capabilities, the failure class is a failed assertion or a collection error reported as a non-zero exit, and the test reads the checkout and writes no file; readOnlyRootFilesystem true, runAsNonRoot true and capabilities.drop ALL hold.
- The open state of alert 213 is not checked: no tool of this run reads code scanning, so the Security Scan step of the pull request and the scan of group 2 show the result.
- find_issues with `tf/azure` lists #4409, #4948, #4949, #5074 and #5076 as open items that share the module, and the plan writes each as an overlap rather than the blocking form, because `devops roadmap plan-check` reports the rule `issue-dependency` for an open issue that a plan names as a dependency.

## Existing Tool Considered

The AzureRM Terraform provider supplies the network_policy argument of the AKS network profile, python-hcl2 through parse_hcl_directory reads the module in process, and the pinned Trivy runs the config scan that group 2 records; the change adopts these three and builds no custom code.

## Dependencies

- #4409 shares tf/azure/main.tf and judges the same CRITICAL AZU-0041 alert; this item delivers its AZU-0041 part, and the other 51 alerts stay with it.
- #4948 shares tf/azure/main.tf and judges AZU-0042 in the same module, so the two edits must not share one branch.
- #4949 shares tf/azure/main.tf and judges AZU-0043 in the same module, so the two edits must not share one branch.
- #5074 shares tf/azure/main.tf and moves the azurerm provider to 5.x, so the two edits must not share one branch.
- #5076 shares the Azure module folder through tf/azure/versions.tf and moves the provider pins, so the two edits must not share one branch.
