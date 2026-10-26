# Tasks

## 1. The pins reach the fixed release

- [x] 1.1 Write the failing tests `test_cloudflared_deployment_runs_a_release_that_rejects_the_compromised_emudhra_intermediates` and `test_cloudflared_tools_lock_installs_a_release_that_rejects_the_compromised_emudhra_intermediates` in `tests/test_k8s_cloudflared.py`, and see them fail before the bump with `uv run devops ci test tests/test_k8s_cloudflared.py`
- [x] 1.2 Set the image tag in `k8s/cloudflared/deployment.yaml` and the `version`, each `url` and each `sha256` of the `cloudflared` entry in `src/devops_cli/tools_lock/tools.lock` to 2026.10.4, with each `sha256` from the `digest` of its release asset and checked against the release notes (for a macOS build, the binary inside the archive); verify with `uv run devops ci test tests/test_k8s_cloudflared.py tests/test_tools_lock.py tests/test_install_tools.py tests/test_stack_dashboards.py`
- [x] 1.3 Regenerate the documentation; no command, option or message changes, so nothing changes; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- #2323 makes Renovate update the image tags of the manifests under `k8s/`, which its `kubernetes` manager does not match by default. This change does not do it, because it changes how many pull requests the repository gets.
- Pending a person: after the merge, Argo CD rolls out Deployment `cloudflared/cloudflared`. Confirm that both pods are Ready and that the alert `CloudflareTunnelDegraded` does not fire.
- Pending a person: upgrade each cloudflared instance outside this repository to 2026.10.2 or later. Networking > Tunnels in the Cloudflare dashboard lists each connector and its version.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
