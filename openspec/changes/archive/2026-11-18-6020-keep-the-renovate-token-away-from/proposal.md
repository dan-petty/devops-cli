# Proposal

## Why

A `postUpgradeTasks` command of the Renovate CronJob (#4905) runs as user 12021 in the container that reads the installation token, and that token holds contents: write and workflows: write on every repository of the App installation. A bad task or a bad upstream release can read /token/github-token and send it out over public HTTPS, so the claim of ADR 0027 that a repository command reaches no key is false for the token (#6020).

## What Changes

- The `config.js` of `k8s/devops/renovate/configmap.yaml` reads `/token/github-token` into the config, removes that file, and exports the token under the quoted key `'token'`, and container `renovate` mounts the volume `token` writable in `k8s/devops/renovate/cronjob.yaml`.
- `src/devops_cli/k8s/renovate_token.py` holds `RENOVATE_TOKEN_PATH` and `token_file_problems`, the rule that the script reads the token path and removes it after the read.
- `tests/invariants/test_k8s_renovate.py` runs the script with `node` and proves that a child process that opens the token path fails with `ENOENT`.
- `tests/gate/k8s_checks/renovate.py` makes the `k8s` row of `devops ci` fail a config that keeps the token or a `token` mount that is read-only.
- ADR 0027 names the installation token in the memory of the Renovate process, with its one hour of life, as a bad consequence and drops the claim that a repository command reaches no key, and `tests/invariants/test_k8s_renovate.py` holds the body to that text.
- `docs/CLUSTER.md` states the removal, the writable mount and the node setting that a person confirms.
- The change carries a spec delta of `renovate-service`, because it changes the CronJob, its config and the rule that holds a task away from the token.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `renovate-service`: Only the token init container reads Secret renovate, A post-upgrade task cannot open the installation token

## Impact

- Code: `src/devops_cli/k8s/renovate_token.py`, `k8s/devops/renovate/configmap.yaml`, `k8s/devops/renovate/cronjob.yaml`
- Documents: `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, `docs/CLUSTER.md`
- Tests: `tests/invariants/test_k8s_renovate.py`, `tests/gate/k8s_checks/renovate.py`

## Feasibility

- `probes` gives `The path `k8s/devops/renovate/cronjob.yaml` is a file of the staging commit.` and `These files of the commit are candidates: `k8s/devops/renovate/configmap.yaml`, `k8s/devops/searxng/configmap.yaml`. No commit in the history deleted or renamed it.`, and it gives `The path `config.js` is no file of the staging commit. No commit in the history deleted or renamed it.`
- `list_files` of `k8s/devops/renovate` shows the four manifests and the kustomization, so the issue's `configmap.yaml` and `networkpolicy.yaml` are files of that folder and `config.js` is no file of its own.
- `read_file` of `k8s/devops/renovate/configmap.yaml` shows the read with no removal at `k8s/devops/renovate/configmap.yaml:41:'token': readFileSync('/token/github-token', 'utf8'),` and shows the key at `k8s/devops/renovate/configmap.yaml:35:config.js: |`, so the issue's `config.js` is a key of ConfigMap `renovate-config`.
- `read_file` of `k8s/devops/renovate/configmap.yaml` shows the empty allow list at `k8s/devops/renovate/configmap.yaml:58:"allowedCommands": [],` and the reason at `k8s/devops/renovate/configmap.yaml:16:container that can read the installation token, so #6020 keeps the token away from the tasks`, so the task and the token live in one container today and no task runs yet.
- `read_file` of `k8s/devops/renovate/cronjob.yaml` from line 170 shows the token mount read-only at `k8s/devops/renovate/cronjob.yaml:184:mountPath: /token` with `k8s/devops/renovate/cronjob.yaml:185:readOnly: true`, so container `renovate` cannot remove the file at this commit.
- `read_file` of `src/devops_cli/config/constants.py` gives the staged value of `CONST_RENOVATE_GITHUB_APP_TOKEN_PERMISSIONS`: `src/devops_cli/config/constants.py:1658:"contents": "write",` and `src/devops_cli/config/constants.py:1663:"workflows": "write",`, which is the reach of the token that the change keeps out of a task.
- `read_file` of the record shows the false sentence at `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md:57:- Good, because a repository command that goes wrong reaches no key and no internal service.` and shows that its front matter holds `status: proposed` and no `body-hash`, so the body changes in place and no hash is updated.
- `read_file` of `docs/CLUSTER.md` shows the sentence to replace at `docs/CLUSTER.md:263:#6020 keeps the token away from the tasks, and then turns them on again.` and the ownership that makes the removal possible at `docs/CLUSTER.md:260:It runs as the Renovate user, so that user owns the token file (mode 0600).`
- `read_file` of `tests/invariants/test_k8s_renovate.py` shows the Renovate module of the staged tree, with the rule of the newer direction at `tests/invariants/test_k8s_renovate.py:5:and of kube-linter, and no test asserts a value of them (#6060).`, so the new case runs the script and asserts its behavior instead of a value of a manifest.
- `read_file` of `tests/gate/k8s.py` shows that the `k8s` row runs each `check_*` function of the folder at `tests/gate/k8s.py:11:import tests.gate.k8s_checks as k8s_checks`, and `read_file` of `tests/gate/k8s_checks/devops_runtime.py` shows the shape of a check and the rendered overlay at `tests/gate/k8s_checks/devops_runtime.py:29:overlay = K8S_DIR / "overlays" / "homelab" / "devops"`.
- `file_symbols` of `tests/gate/k8s_render.py` shows `applied_documents` and `kustomize`, so a new check reads the rendered documents of the devops overlay as the other checks of the row do.
- `search_code` of `renovate-config` shows the ConfigMap name at `k8s/devops/renovate/configmap.yaml:25:name: renovate-config`, and `search_code` of `token_file_problems` finds no match, so the rule is new.
- `applied_documents` of `tests/gate/k8s_render.py` needs a checkout of the repository and the `kubectl` binary, and `kubectl` is `NOT_IN_RUNNER`: the `k8s` row runs in the Static Analysis job of the pull request and never in a runner pod.
- `token_file_problems` needs no checkout, no client and no network, because it reads the text of the script.
- The new case of `tests/invariants/test_k8s_renovate.py` starts `node` in pytest's temporary folder: it needs a checkout of the repository and the `node` binary, which the runner image holds, and it reaches no network and no cluster.
- The `node` run writes only under pytest's temporary folder, as the `check_*` cases of the row do; the runner pod sets `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`, `allowPrivilegeEscalation: false`, `runAsNonRoot: true` and `seccompProfile: RuntimeDefault`, and the plan changes none of them.
- The plan introduces no command of its own: the verifies run `uv run devops ci test`, `uv run devops ci --check --only k8s` and `uv run devops ci docs`, so the failure classes are `test`, `lint` and `types`.
- The node's `kernel.yama.ptrace_scope` is `not checked` by this run: a person confirms it on the cluster with `kubectl debug node/<worker-node> -- chroot /host sysctl kernel.yama.ptrace_scope`, which must print 1.
- The first checks of the implementation against the real system are `uv run devops ci test tests/invariants/test_k8s_renovate.py`, `uv run devops ci --check --only k8s` and `uv run devops ci docs`.
- This reply answers the reported fault: the failing test is now a case of `tests/invariants/test_k8s_renovate.py`, a file of the staged commit, and no group creates a test module.
- The exposure is current and waits on no other item: the staged CronJob sets no `RENOVATE_DRY_RUN` and the item that turns the tasks on comes after this change.

## Existing Tool Considered

No tool covers the need: the alternatives check in the item records `containers/bubblewrap` as rejected by ADR 0018, because it needs user namespaces that this pod refuses, has no hook into the task spawner of Renovate, and leaves the token in the Renovate process memory. The change builds the `config.js` removal, one rule module, one check of the `k8s` row and the offline run of the script itself: about 4k tokens to build, 300 tokens per later change to keep, and 2k tokens to fix, over about 4 hours. It deletes no internal code.

## Dependencies

None.
