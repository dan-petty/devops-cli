# Proposal

## Why

`devops k8s teardown-stack` stops before it removes cluster resources when a post-Helm manifest kind is not installed (#1818).
On a cluster where a CustomResourceDefinition never installed, `kubectl delete -f <file> --ignore-not-found` exits 1.
`devops k8s deploy-stack` swallows the matching apply failure because it runs with `check=False`.
Checking whether the cluster serves the kind avoids unexpected teardown aborts and reports unapplied post-Helm manifests.

This change fits in one pull request.

## What Changes

- Check `kubectl api-resources` for the manifest's `apiVersion` and `kind` before deleting post-Helm manifests in `devops k8s teardown-stack`.
- Skip deleting a post-Helm manifest when the cluster does not serve its kind, and print a warning message.
- Check `kubectl api-resources` before applying post-Helm manifests in `devops k8s deploy-stack`.
- Skip applying a post-Helm manifest when the cluster does not serve its kind, and print a warning message.
- Add standard message templates for skipped post-Helm deletions and failed post-Helm applies in `devops_cli.lang.en.messages`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `k8s-helm-deploy`: Add requirement and scenarios for verifying that the cluster serves post-Helm manifest kinds during teardown and deployment.

## Impact

- Command `devops k8s teardown-stack` does not fail when CRDs are missing.
- Command `devops k8s deploy-stack` reports post-Helm manifests whose CRDs are not installed.
- Affected code: `src/devops_cli/commands/k8s/stack_lifecycle.py` and `src/devops_cli/lang/en/messages.py`.
- Affected tests: `tests/test_k8s.py`.

## Feasibility

We confirmed the premise against `src/devops_cli/commands/k8s/stack_lifecycle.py` and upstream `kubectl` behavior:
- `_delete_post_helm_paths` calls `runtime._run_cmd` with `check=True`.
- `kubectl delete -f <file> --ignore-not-found` ignores missing object instances.
- Upstream Kubernetes documentation confirms that `--ignore-not-found` does not ignore missing CustomResourceDefinitions.
- When an API group is missing, `kubectl delete` exits 1 with `no matches for kind`.
- `kubectl api-resources --api-group=<group>` lists served resources and outputs exit code 0.
- `_apply_manifest_files` runs `kubectl apply -f` with `check=False`, which silences apply failures when CRDs are missing.

## Existing Tool Considered

We considered `kubectl delete --ignore-not-found` without an API check. Upstream documentation confirms that this flag does not ignore missing API groups.
We considered catching execution errors from `kubectl delete`. Catching subprocess errors masks other cluster failures and violates project guidelines.
We considered inspecting CRDs through `kubectl get crd`. `kubectl api-resources` is the standard tool that checks both built-in kinds and CRDs.
Using `kubectl api-resources` adds no dependencies and uses the existing `kubectl` binary.
No internal code is deleted.
