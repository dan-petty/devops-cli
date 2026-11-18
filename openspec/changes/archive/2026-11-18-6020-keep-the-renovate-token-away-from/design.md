# Design

## Decisions

- **Read the token in `config.js` and remove the file before the config is exported.**: `config.js` runs once at start, before Renovate processes a repository or runs a task, and Renovate needs the token in its config.
- **Mount the volume `token` writable in container `renovate`.**: Init container `token` already writes the file as user 12021, so that user can unlink it once the mount is not read-only, and no other container reads the path.
- **Let the script read the path from `DEVOPS_CLI_TOKEN_FILE`, with `/token/github-token` as the default.**: The case can then run the shipped script with no root and no rewrite of its text, and the rule and the `k8s` row hold the default path in place.
- **Keep `allowedCommands` empty in this change.**: Comment 3 of the item names the upgrade tasks to turn on after this one, and this change delivers the reach of the token only.
- **Rely on the dropped capabilities and on `kernel.yama.ptrace_scope` of the node for the copy in memory.**: The pod drops all capabilities and uses `RuntimeDefault` seccomp, so it holds no `CAP_SYS_PTRACE`, and a node at `ptrace_scope` 1 refuses a trace of a non-descendant.
- **Correct the body of ADR 0027 in place.**: The record is `proposed` and holds no `body-hash`, and the decision itself stays in force.
- **Hold the manifest rule in the `k8s` row and prove the removal offline by running the script with `node`.**: A test that asserts a value of a manifest is being removed (#6060), a validator row is the allowed proof of a manifest change, and the offline run needs no cluster and no new command.
- **Put the offline case in `tests/invariants/test_k8s_renovate.py`, the Renovate module of the staged tree.**: The module already holds the Renovate records, so the change creates no test module and its test path names a file of the commit.
- **Keep the rule that the script reads the path before it removes it in `src/devops_cli/k8s/renovate_token.py`.**: The `k8s` row and the offline case then apply one rule, as a check applies the rules of `devops_cli.k8s.cluster_job`.

## Rejected alternatives

- **Keep `allowedCommands` empty instead of removing the token file.**: The config already holds this and it stops the upgrade work of the repositories, and the item asks for the token to be out of reach before the tasks come back.
- **Pass the token through an environment variable.**: A child process inherits the environment of Renovate, so a task reads the token at once.
- **Run each task in a second container without `/token`.**: Renovate runs `postUpgradeTasks` in its own container, and `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md:40:A patch to the image is a new decision.`
- **Wrap each task with bubblewrap.**: The alternatives check records `containers/bubblewrap` as rejected by ADR 0018, and it needs user namespaces that the `RuntimeDefault` profile of the pod refuses.
- **Ship a `Localhost` seccomp profile that denies `ptrace`.**: The profile file must exist on each node, and the repository ships no node-level seccomp profile.
- **Add only a `Status History` line to ADR 0027.**: It leaves the false sentence at `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md:57:- Good, because a repository command that goes wrong reaches no key and no internal service.` in the body.
- **Supersede ADR 0027 with a new record.**: The decision of ADR 0027 stays in force, so a new record would supersede it for no reason.
- **Add a manifest invariant test that compares a value of the CronJob or the ConfigMap.**: `tests/invariants/test_k8s_renovate.py:5:and of kube-linter, and no test asserts a value of them (#6060).`
- **Create a new test module `tests/k8s/test_renovate_token.py` for the offline run.**: The plan check refuses a test path that names no file of the staged commit, and the case fits the Renovate module that the tree already holds.
- **Add a live check command that starts a pod on the cluster and reads the token path there.**: `list_files` of `src/devops_cli/commands/k8s` holds no module for such a command, so the change would add a command, a client of the cluster and a test of both, while the offline run of the script proves the same property with no cluster.

## Security

The installation token crosses a trust boundary: init container `token` writes it to a memory emptyDir that container `renovate` mounts, and a `postUpgradeTasks` command runs as the same user in that container. The change keeps the token out of the file system before Renovate processes a repository, and it relies on the dropped capabilities and on the node's `kernel.yama.ptrace_scope` of 1 for the copy in the process memory. A person must confirm on the cluster that `kubectl get configmap renovate-config -o yaml` shows the script that removes the file, and that `kubectl debug node/<worker-node> -- chroot /host sysctl kernel.yama.ptrace_scope` prints 1. The case `test_the_config_removes_the_token_before_a_child_process_can_read_it` fails when the script stops removing the file, and the `k8s` row of `uv run devops ci --check --only k8s` fails a config that keeps it or a `token` mount that is read-only.
