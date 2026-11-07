# Proposal

## Why

Issue #4086 is group 1 of #3769. The tests of `tests/commands/k8s/` patch names inside `devops_cli`, and #1336 turns that into a ban.

The tree at `origin/main` 74ba76b8 holds these facts. They were counted again, because the text of #3769 is older than the tree.

- 342 calls of `patch` or `monkeypatch.setattr` take a string that starts with `devops_cli` as their first argument. They sit in 11 files, and `test_k8s.py` holds 199. `git grep` finds 245 lines of them, because a call that wraps onto several lines has its string on another line than its `patch(`. `test_k8s_rbac_audit.py` adds 8 patches of one constant, `_RUN_CMD`, that `git grep` does not find.
- The patches name `_run_cmd`, `_cluster_reachable`, `_minikube_running`, `_is_cluster_argo_managed`, `_verify_url_reachability`, `run_subprocess`, `sync_k8s_credentials`, `push_for_stacks`, `require_keyring_for_push`, `port_forward`, `configure_urls`, `save_settings`, `load_settings` and the four scanner functions.
- `commands/k8s/__init__.py` holds `_K8sModule`, a module class that forwards an attribute a test sets to the submodule that uses it. Only these tests need it. `docs/TESTING.md` forbids product code shaped so that a test can patch it.
- Three commands reach their edge in a way that no fake covers. `contexts` and `status` load the Kubernetes SDK themselves, and `_launch_port_forwards` calls `subprocess.Popen`. The test of each patched the helper in front of the edge.

## What Changes

- The k8s command tests install no patch of a `devops_cli` name. Each reaches its edge through a shared fake: `process_fake` for kubectl, helm and minikube, the `cluster` fixture for the Kubernetes API and the Argo CD Application, `web` for Loki and the Prometheus proxy, `scanner_fake` for kube-linter, Popeye, Pluto and kubeconform, `keyring_store`, `clock`, and the `config` fixture. A test keeps its name and the behavior it checks.
- `tests/support/tcp_probe.py` adds the `tcp_probe` fixture. Code asks whether an address accepts connections with `socket.create_connection`, and no seam reaches that call. The fixture replaces it, as `docs/TESTING.md` allows for a stdlib edge, refuses every probe until a test makes an address listen, and records each probe.
- `tests/support/k8s_commands.py` holds the answers that several test files share: the Ingress list, the Helm version, the state of Minikube, the world of kubectl for a Secret push, the keyring values of a push, and the Argo CD Application.
- Product code that only the patches needed is deleted:
  - `_K8sModule`, `_forward_submodule_attr`, `_PATCH_TARGET_MAP` and the three name sets in `commands/k8s/__init__.py`. The package now exports `app`. `commands/kustomize.py` imports `_validate_k8s_identifier` from its module.
  - `_k8s_clients` in `commands/k8s/cluster_runtime.py`, and its two tests. `contexts` and `status` now read through `KubernetesService` (`list_contexts` and `list_nodes`), like the other commands of the group, so the `cluster` fake reaches them.
  - The `subprocess.Popen` call of `_launch_port_forwards`. It starts the forward through `spawn_detached` with `isolate_env=False`, which keeps the ambient environment that the call had. This is the seam that `docs/TESTING.md` names for a detached child. The two tests of `tests/k8s/test_k8s_port_forward_daemon.py` that read the source of `networking.py` or replaced its `subprocess` name now use `process_fake`.
- `tests/commands/k8s/test_k8s.py` keeps every test. The tests of the pods table and of `devops k8s pods --watch` also lose their patches of `KubernetesService.get_instance`, of the Kubernetes SDK and of the private names of `ui/data_providers.py`.
- Tests that changed, and why:
  - `test_k8s_contexts_and_switch` and `test_k8s_logs_logql_query_dispatch` now check the marked active context and the `since` and `limit` of the Loki query. The mutations of these two lines survived the old assertions.
  - `test_deploy_and_teardown_stack_use_effective_context` deploys the `logging` stack. The old test hid a defect of the `infra` stack with a patch of `sync_k8s_credentials` (#4091).
  - `test_k8s_helpers_and_error_branches` lost its case of an unreadable kubeconfig to the new test `test_k8s_contexts_fail_when_the_kubeconfig_is_unreadable`. A test cannot read the real kubeconfig source and the `cluster` fake together.
  - The two tests of `_k8s_clients` are deleted with the function.
- Deleted: the plan folder `openspec/changes/1323-k8s-commands-edge-fakes`. Its issue closed with only the plan merged, its tasks name fixtures that do not exist (`fake_cluster`), and this change does its test and `_K8sModule` parts.
- No ceiling file counts string patches of `devops_cli` names, so no ceiling goes down. `tests/invariants/test_source_tree.py` gets a test that holds `tests/commands/k8s/` to zero string patches of a `devops_cli` name, so a patch cannot return. A group joins its list when it removes its last patch. #1336 owns the ban for the whole of `tests/commands`.
- This change alters no behavior a consumer observes. The commands, their options and their messages are the same. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request. The other three groups of #3769 are other issues.

## Impact

- `src/devops_cli/commands/k8s/` (`__init__.py`, `cluster_context.py`, `cluster_runtime.py`, `networking.py`) and `src/devops_cli/commands/kustomize.py`.
- `tests/commands/k8s/` (11 files with patches, and `test_k8s_rbac_audit.py`), `tests/k8s/test_k8s_port_forward_daemon.py`, `tests/invariants/test_source_tree.py`, `tests/support/tcp_probe.py` and `tests/support/k8s_commands.py` (new).
- `docs/TESTING.md`.

## Feasibility

Checked on `origin/main` 74ba76b8, 2026-11-07. The premise of #3769 holds for this group, with the tree changes below.

- Counts: an `ast` walk over `tests/commands/k8s/*.py` finds 342 string patches. Adding the 8 patches of `_RUN_CMD` gives 350 before the change and 0 after. The 524 test ids that `uv run pytest tests/commands/k8s --collect-only -q` lists before the change are all present after it, except the two deleted tests of `_k8s_clients`, and one new test splits off `test_k8s_helpers_and_error_branches`.
- Every edge has a fake: `uv run pytest tests/commands/k8s/test_k8s_tempo.py` already runs a full `deploy-stack` over `cluster`, `process_fake` and `keyring_store`, and `tests/commands/test_k8s_validate.py` runs kubeconform over `scanner_fake`.
- `process_fake` answers `kubectl cluster-info` with success when a test scripts nothing, so a test that needs an unreachable cluster scripts `kubectl cluster-info` with exit code 1, and `cluster.unreachable()` for the API.
- `uv run python -c "import devops_cli.commands.k8s"` finds `app` after `_K8sModule` is gone, and `rg -n "commands\.k8s\.[A-Za-z_]+\"" tests` finds no patch of the package namespace outside this group. The other tests patch the submodules, so the forwarding class served this group alone.
- Mutation check, run on the product code and restored: the Helm minimum version check, the Helm `uninstall` of a pending install, the `Running` check of Minikube, the check of an unreachable cluster, the Argo CD check, the start of the port-forward child, the active context mark, the flags of the post-deploy networking, the loopback fallback of a service URL, the domain render of a manifest, the node read of `status`, the model removal of `ollama prune`, the `since` of a Loki query and the Argo CD refusal of `teardown-stack` each fail a migrated test.
- The migration found one defect, and the old patch hid it: `fetch_secret_data` checks a kubeconfig context with the RFC 1123 rule, so `deploy-stack --stack infra` exits with 1 on an EKS ARN after it deployed. #4091 holds it.
- 78 imports of a private `devops_cli` name remain in the group (79 before). They are tests of private helpers, such as `_parse_minikube_service_url`. Moving that logic into a domain package is another item.

## Existing Tool Considered

The shared fakes of #1307 (`process_fake`, `cluster`, `web`, `scanner_fake`, `keyring_store`, `clock`, `config`) cover every edge of these tests but one. They lack a double for a TCP probe. `pytest-socket` blocks sockets and does not answer them, and `pytest-mock` patches, which the project forbids. The change builds `tcp_probe` instead: about 70 lines over a stdlib attribute, as `docs/TESTING.md` allows. The cost is about 5,000 tokens to write and about 500 tokens each month to keep. The change deletes `_K8sModule`, `_k8s_clients`, the `Popen` call, the hand-made stand-ins `_mock_proc`, `_mock_completed` and `_kubectl` of the RBAC test, and the stale plan of #1323.
