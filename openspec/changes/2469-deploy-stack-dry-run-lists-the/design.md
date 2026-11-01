# Design

## Decisions

- **`helm_commands` is a list of argument lists (`list[list[str]]`) in the `details` of the dry run.** Each element has the shape that `runtime._run_cmd` receives and that `_build_helm_upgrade_cmd` returns. A test compares exact arguments and parses no string.
- **The list holds the repository commands first, then the upgrade commands.** This is the order of the real run: `helm repo add` for each repository, `helm repo update`, then `helm upgrade --install` for each release. The list holds no read (`helm version`, `helm status`), because the dry run does not make it.
- **`_build_helm_repo_cmds(selected_stacks)` returns the repository commands, and `_deploy_helm_repos` runs them.** The real run and the dry run use one builder, so a change of the builder changes both. For a stack without a repository, the builder returns an empty list, and `_deploy_helm_repos` returns early as it does now.
- **The dry run builds `helm_ctx` from `effective_context` before the dry-run branch.** The line moves up. The real run reads the same variable after the branch. The dry run then carries `--kube-context` when a context is set, and `--wait --timeout <timeout>` when `wait` is true.
- **The dry run passes `is_v4=False`.** It runs no `helm version`, because a dry run makes no request, reads included (#412). On Helm 4 or later the real run adds `--force-conflicts`. The spec states this limit, so the dry run does not claim more than it knows. The dry run also lists the commands as for a cluster that Argo CD does not manage, as `helm_releases` already does, because it cannot read the cluster.
- **`helm_releases` stays.** It lists the release names, as the base spec scenario of the chat stack and `tests/commands/k8s/test_k8s.py:2811` read it. It is not a request, so `helm_commands` does not replace it.
- **The parity requirement is tested through the process edge, not through a private name.** A test runs the real `deploy-stack` over `process_fake`, collects the `helm repo` and `helm upgrade` argument lists, and compares them with `details.helm_commands` of the dry run for the same options. No test calls `_build_helm_upgrade_cmd`.

## Rejected alternatives

- **Joined command strings.** A test must split them again to check a flag, and the argument boundaries are lost. The argument list has the type of the builder result.
- **Replace `helm_releases` with `helm_commands`.** The base spec and one test read the names. The commands do not give the names as a plain list, so the removal adds work that the issue does not ask for.
- **Omit `helm repo update`.** The real run makes this request, and #412 says that the dry run lists every request the real run makes.
- **Run `helm version` in the dry run to set `is_v4`.** It starts a process and reads state. #412 forbids a read in a dry run, and the output would change with the Helm on the host.
- **Call `_build_helm_upgrade_cmd` in a test to prove the parity.** It needs a private import, which docs/TESTING.md bans, and the call runs `helm version` when `is_v4` is not set. The process fake shows what the real run starts.
- **Move all 11 test files off the private tables.** The issue asks that a test can read the values from the dry run. The other files test other subjects, and a change of them is a separate item.
