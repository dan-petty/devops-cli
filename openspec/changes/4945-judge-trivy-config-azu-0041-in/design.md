# Design

## Decisions

- **Set network_policy = "azure" in the network profile of the AKS cluster.**: The cluster sets the Azure CNI plugin at `tf/azure/main.tf:68:network_plugin = "azure"`, and the Azure policy engine is the engine native to Azure CNI, so the module needs no third-party engine and no extra provider.
- **Read the module in the test with parse_hcl_directory instead of a hand-rolled block reader.**: `src/devops_cli/tf/analysis.py:189:def parse_hcl_directory(directory: Path) -> IaCConfiguration:` already parses HCL on the pinned python-hcl2 dependency, so a second parser would be code to keep and fix for no gain.
- **Judge the alert by changing the module, with no ignore entry and no dismissal.**: `SECURITY.md:87:1. Fix the file in a pull request that closes the issue. This is the first choice.` makes the fix the first choice, `SECURITY.md:88:never for a CRITICAL alert, never for a secret.` refuses an ignore of this alert, and `SECURITY.md:89:3. A person dismisses the alert in code scanning, with a reason. An agent does not dismiss an alert.` keeps a dismissal to a person.
- **Deliver the AZU-0041 criterion with the scan process of group 2 and not with a test.**: `docs/TESTING.md:76:No test starts a real security scanner either` refuses a test that starts a scanner, and the runner capabilities list trivy as NOT_IN_RUNNER, so a person runs the pinned Trivy and the Security Scan step of the pull request runs it too.
- **State the AZU-0041 condition in the spec delta as the network profile setting, not as a scanner run.**: A scenario must be assertable offline, and the new invariant test asserts the setting; the scan itself is the process of group 2 and the check of the pull request.
- **Place the new test in tests/invariants/.**: The test asserts an invariant of a shipped module rather than a function of one package, and `tests/invariants/` is the folder for such a check.
- **Treat the OpenTofu and Trivy commands of group 2 as a person's commands, since the runner image holds neither binary.**: The image tools list of the runner capabilities holds no `tofu` and the excluded-tools list holds no `tofu` entry, and `docs/DEVCONTAINER_USAGE.md:38:the image ships neither` says the project image installs no OpenTofu binary; trivy is an excluded tool with the entry that a Job cannot run the IaC scan.
- **Name the open items that share tf/azure/main.tf as overlaps and give none the blocking form.**: `devops roadmap plan-check` reports the rule `issue-dependency` for an open issue that a plan names as a blocking dependency, and all five items are open.

## Rejected alternatives

- **Add a time-limited entry to .trivyignore.yaml for AZU-0041.**: `SECURITY.md:88:never for a CRITICAL alert, never for a secret.` refuses an ignore of this alert, and the change needs no unreleased fix.
- **Dismiss alert 213 in code scanning with a reason.**: `SECURITY.md:89:3. A person dismisses the alert in code scanning, with a reason. An agent does not dismiss an alert.` keeps the dismissal to a person.
- **Set the network policy to calico or to cilium.**: Calico adds a third-party engine and Cilium needs a different dataplane and plugin, while `tf/azure/main.tf:68:network_plugin = "azure"` selects Azure CNI, whose native engine is Azure.
- **Parse the network profile block with a brace matcher written for the test.**: `src/devops_cli/tf/analysis.py:189:def parse_hcl_directory(directory: Path) -> IaCConfiguration:` already returns the block attributes, so the hand-rolled reader would duplicate tested code.
- **Write a spec scenario that runs the real Trivy config scan.**: `docs/TESTING.md:76:No test starts a real security scanner either` refuses a test that starts a scanner, and trivy is NOT_IN_RUNNER, so the scan is the process of group 2 and not a scenario that a test asserts.
- **Leave the AZU-0041 result to a person with no task in the plan.**: The review of the earlier plan refused that as `criterion_dropped`: the criterion that the configuration produces no AZU-0041 alert needs a task that runs the scan or records its result.
- **Claim that the Security Scan step of the pull request fails when AZU-0041 returns.**: `.github/workflows/ci.yml:96:run: uv run devops scan report --sarif .data/scan.sarif --skip bandit,trivy` sets no severity threshold and no fail-on option, so the step uploads the result and does not fail on it.
- **State that the excluded-tools table names `tofu` as NOT_IN_RUNNER.**: The runner capabilities list no `tofu` entry in the excluded tools and none in the image tools, so the plan states the absence of a binary in the image and cites `docs/DEVCONTAINER_USAGE.md:38:the image ships neither` instead.

## Unchanged references

- `src/devops_cli/commands/sandbox.py` (identifier): The network_policy function of the sandbox command is a different identifier from the Terraform argument that the plan adds; the plan renames and removes nothing.

## Security

Nothing leaves the repository: the change edits a committed OpenTofu module and adds a test that parses it in process, with no secret, no credential, no network and no cluster. A person must confirm that the workloads of the AKS cluster stay reachable once the Azure network policy engine is on, because the engine drops each flow that no Kubernetes NetworkPolicy object admits, and that the owner records the decision on the CRITICAL alert 213, since an agent neither dismisses nor ignores it. `tests/invariants/test_azure_aks_network_policy.py` fails if the network profile loses the Azure engine, and the Trivy-config scan reports AZU-0041 again if the engine is dropped.
