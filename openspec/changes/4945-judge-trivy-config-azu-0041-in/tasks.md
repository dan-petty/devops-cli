# Tasks

## 1. Set the Azure network policy on the AKS cluster and assert it with an invariant test

Reads: `tf/azure/main.tf`, `src/devops_cli/tf/analysis.py`, `tests/support/paths.py`, `tests/tf/test_tf_analysis.py`. Changes: `tf/azure/main.tf`, `tests/invariants/test_azure_aks_network_policy.py` (new).

- [ ] 1.1 Write `tests/invariants/test_azure_aks_network_policy.py` first, and run the group verify to watch it fail on the base tree. The test joins REPO_ROOT from `tests/support/paths.py` with the `tf/azure` folder, parses that folder with parse_hcl_directory from `src/devops_cli/tf/analysis.py`, selects the resource whose address is azurerm_kubernetes_cluster.aks, and asserts that the first entry of its network_profile list sets network_plugin to azure and network_policy to azure. Then add network_policy = "azure" to the network_profile block of the AKS resource in `tf/azure/main.tf`, beside network_plugin = "azure", and run the verify again to watch it pass. The test starts no program, reaches no network and writes no file
  - Verification: `$ uv run devops ci test tests/invariants/test_azure_aks_network_policy.py` passes

## 2. Record the network policy, the validation and the cleared AZU-0041 result for the Azure module

Reads: `tf/README.md`, `tf/azure/main.tf`, `SECURITY.md`. Changes: `tf/README.md`.

- [ ] 2.1 Edit `tf/README.md` to name the Azure policy engine of the AKS cluster and the reason it is on, to give the devops tf init and devops tf validate commands of the module, and to record that the Trivy config scan of `tf/azure` reports no AZU-0041 result for `tf/azure/main.tf`. Then run the two OpenTofu commands and the pinned Trivy's config scan on the module folder, and confirm the three results, and run this check by hand: On a host that holds OpenTofu, the pinned Trivy and the network that fetches the azurerm provider, run devops tf init tf/azure and devops tf validate tf/azure, and confirm that each command exits with status 0. Run trivy config tf/azure --format json --quiet and confirm that its output holds no AZU-0041 result for tf/azure/main.tf. Confirm that the Security Scan step of the pull request uploads no AZU-0041 result, and that code scanning shows alert 213 fixed after the merge.
- [ ] 2.2 Edit `tf/README.md` to name the Azure policy engine of the AKS cluster, to give the devops tf init, devops tf validate and trivy config commands of the module, and to record the cleared AZU-0041 result
  - Verification: `$ uv run devops ci docs` passes
