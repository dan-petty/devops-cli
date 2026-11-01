# Proposal

## Why

#2469: `devops k8s deploy-stack --dry-run` gives only the release names in `details.helm_releases`. It does not list the `helm repo add`, `helm repo update` and `helm upgrade --install` commands that the real run makes. A person cannot check the chart, the version and the repository from the output. A test of these values must read the private tables `_HELM_RELEASES_BY_STACK` and `_HELM_REPOS_BY_STACK`, and docs/TESTING.md says that no test imports a private name. The dry-run rule (#412) says that a dry run returns the requests that the real run would make.

## What Changes

- Add the key `helm_commands` to the `details` of the `deploy-stack` dry run. It is a list of argument lists: first each `helm repo add` and the `helm repo update`, then one `helm upgrade --install` for each release, in the order of the real run.
- Extract `_build_helm_repo_cmds(selected_stacks)` from `_deploy_helm_repos`. The real run and the dry run build the repository commands from it. The upgrade commands come from `_build_helm_upgrade_cmd`, which both paths already share.
- Move the `helm_ctx` line of `deploy_stack` above the dry-run branch, so the dry run adds `--kube-context` as the real run does. The dry run passes `wait` and `timeout` to the builder.
- The dry run runs no command, `helm version` included, because a dry run makes no request and reads no state (#412). It builds the upgrade commands with `is_v4=False`. On Helm 4 or later the real run adds `--force-conflicts`, which the dry run cannot know.
- Keep `helm_releases`. It is a list of names, not a request. The base spec scenario of the chat stack and the test at `tests/commands/k8s/test_k8s.py:2811` read it. This is not a compatibility shim.
- Add the failing tests first to `tests/commands/k8s/test_k8s_logging_stack.py`, then change the two tests of that file that read private tables so that they read the dry-run output.
- The change has a spec delta in `k8s-helm-deploy`, because the dry-run output of a devops command is observable.
- The change fits one pull request. It has two task groups.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `k8s-helm-deploy`: ADDED the requirements "deploy-stack dry run lists the Helm repository commands", "deploy-stack dry run lists the Helm upgrade commands", "deploy-stack dry run lists the Helm commands as for Helm 3" and "The Helm commands of a deploy-stack dry run are those of the real run".

## Impact

- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py` (`_deploy_helm_repos`, `deploy_stack`).
- Tests: `tests/commands/k8s/test_k8s_logging_stack.py`.
- Specs: `openspec/specs/k8s-helm-deploy/spec.md`.
- No option, help text or document changes. The help of `--dry-run` (`HELP.k8s.deploy_dry_run`) stays true, so the change regenerates no document.
- Out of scope: the other 10 test files that read the private tables (`git grep -l "_HELM_RELEASES_BY_STACK\|_HELM_REPOS_BY_STACK" -- tests`). They keep working, and the new key lets each of them move later. The issue asks that a test can read the values, not that every test moves.

## Existing code

- Reuse `_build_helm_upgrade_cmd` as it is. Its `is_v4` input is the only input the dry run sets by hand.
- Reuse `render_dry_run_result` and the `details` dict of `deploy_stack`. Keep `helm_releases`, `manifests` and the other keys.
- Keep `_deploy_helm_repos` as the caller that runs the commands. Its calls (`helm repo add` with `check=False`, then `helm repo update`) and its early return for a stack without a repository stay.
- Reuse `tests/support/fakes/process.py` (`process_fake`, `ProcessAnswer`) and the `cli` fixture of `tests/support/cli.py`. The pattern is `test_deploy_stack_with_process_fake_pending_upgrade_rolls_back` in `tests/commands/k8s/test_k8s.py`.
- Tests that must keep passing: `test_infra_dry_runs_list_the_argo_workflows_release_perimeter_and_template` and `test_build_helm_upgrade_cmd_carries_take_ownership` in `tests/commands/k8s/test_k8s.py`, the dry-run class ratchet in `tests/invariants/`, and `tests/invariants/test_k8s_argocd_apps.py`.

## Acceptance

Each criterion of #2469, and the dry-run rule (#412) that the issue rests on, maps to a group of `tasks.md`.

| Criterion of the issue | Delivered by |
| :--- | :--- |
| Dry run lists each `helm repo add` and `helm repo update`, in order | Group 1: the test of task 1.1 and the builder of task 1.2 |
| Dry run lists each `helm upgrade --install` with release, chart, version, namespace and values | Group 1: the test of task 1.1 and the dry-run branch of task 1.2 |
| A test reads chart, version and repository from the dry run, with no private import | Group 2: the two tests of `test_k8s_logging_stack.py` read the dry run |
| The commands come from the builders of the real run | Group 1: the parity test of task 1.1; the shared builders of task 1.2 |
| The dry run makes no request (#412) | Group 1: the same parity test asserts that the dry run starts no `helm` command |

No criterion waits for a person.

## Feasibility

All commands ran on `origin/main` at `aeb699e3`, in the worktree of this change.

- The premise holds. `uv run devops k8s deploy-stack --stack logging --dry-run` prints `"helm_releases": ["loki"]` and `"manifests": ["k8s/logging/networkpolicy.yaml"]`. It has no `helm_commands` key and no helm command.
- The cause is as the issue says. `git grep -n '"helm_releases"' -- src` prints `src/devops_cli/commands/k8s/stack_lifecycle.py:1324`. `git grep -n "render_request_plan\|helm_commands" -- src/devops_cli/commands/k8s/stack_lifecycle.py` prints nothing.
- Nothing newer did it. `git log -S"helm_commands" --oneline origin/main -- src tests` prints nothing. `git diff 8b650a64 origin/main -- src/devops_cli/commands/k8s/stack_lifecycle.py` (8b650a64 is the commit of the issue) changes only the repository and release tables (`grafana-community`, `mattermost`) and not the dry-run branch. A search of the open issues for "deploy-stack dry-run" in the title gives only #2469. #2239 names `deploy-stack` as done, but its request plan covers the Secret push only.
- The real run makes these commands. A process fake run of `deploy-stack --stack logging --no-push-secrets --context ctx-example --k8s-dir k8s` (a scratch test with `process_fake`, Helm 3.17 answered) recorded: `helm version --template {{.Version}}`, `helm repo add grafana-community https://grafana-community.github.io/helm-charts`, `helm repo update`, `helm status loki -n logging -o json --kube-context ctx-example`, and `helm upgrade --install --take-ownership loki grafana-community/loki --version 20.0.2 --namespace logging --values k8s/logging/loki-values.yaml --kube-context ctx-example --wait --timeout 10m`. The repository and upgrade commands are what the dry run must list. `helm version` and `helm status` are reads and stay out of the list.
- The `helm_ctx` problem is real. `git grep -n "helm_ctx = " -- src/devops_cli/commands/k8s/stack_lifecycle.py` prints line 1371 for `deploy_stack`. The dry-run branch returns at line 1340, before that line, so the dry run must build `helm_ctx` from `effective_context` (set at the top of the function) first.
- The `is_v4` input is real. `_build_helm_upgrade_cmd` adds `--force-conflicts` when `is_v4` is true, and it runs `helm version` when `is_v4` is `None`. The dry run therefore passes `is_v4=False`. A dry run makes no request, reads included (`src/devops_cli/dry_run/requests.py`, #412).
- The test paths are real. `git ls-files tests | grep test_k8s_logging_stack` prints only `tests/commands/k8s/test_k8s_logging_stack.py`. The file imports `_HELM_RELEASES_BY_STACK`, `_HELM_REPOS_BY_STACK` and `_MANIFESTS_BY_STACK` on lines 13 to 17, and reads them on lines 32, 33, 49, 62 and 64. The dry-run code is the package `src/devops_cli/dry_run/`, not a module.
- The count is right. `git grep -l "_HELM_RELEASES_BY_STACK\|_HELM_REPOS_BY_STACK" -- tests | wc -l` prints 11 files. The issue says 13, and the difference is of no matter here.
- Only two readers of the `helm_releases` key exist: `tests/commands/k8s/test_k8s.py:2811` and the base spec scenario of the chat stack. The key stays.
- The two new tests fail on the base for the right reason. The dry-run `details` has no `helm_commands` key, so the lookup raises `KeyError: 'helm_commands'`.

## Existing Tool Considered

No open, maintained library covers this need. The dry-run output and the argument builders are project code: `render_dry_run_result` in `src/devops_cli/dry_run/`, and `_build_helm_upgrade_cmd` and `_deploy_helm_repos` in `src/devops_cli/commands/k8s/stack_lifecycle.py`. Helm itself has `helm upgrade --dry-run`, but it asks the cluster, renders the chart and makes requests, so it breaks the rule of #412 that a dry run makes none. The change reuses the existing builders and adds one small function, `_build_helm_repo_cmds`, that the real run also calls. The written cost, as an estimate: about 25,000 tokens to build, about 5,000 tokens to keep and fix it, and under one hour of elapsed time. The change deletes no internal code.
