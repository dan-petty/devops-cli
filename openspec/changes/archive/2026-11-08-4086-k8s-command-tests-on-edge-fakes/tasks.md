# Tasks

## 1. The command layer holds nothing that only a patch needed (refactor)

- [x] 1.1 Delete `_K8sModule`, `_forward_submodule_attr`, `_PATCH_TARGET_MAP` and the three name sets from `commands/k8s/__init__.py`, and export `app` alone
  - Verification: `! git grep -n -F -e _K8sModule -e _forward_submodule_attr -e _PATCH_TARGET_MAP -- src tests`
- [x] 1.2 Read the contexts and the nodes of `contexts` and `status` through `KubernetesService`, and delete `_k8s_clients` and its tests
  - Verification: `! git grep -n -F -e _k8s_clients -- src tests`
- [x] 1.3 Start the forward of `_launch_port_forwards` through `spawn_detached`
  - Verification: `! git grep -n -F -e Popen -- src/devops_cli/commands/k8s`

## 2. The k8s command tests reach their edges through the shared fakes (test-only edits)

- [x] 2.1 Add the `tcp_probe` fixture and the shared answers of `tests/support/k8s_commands.py`
  - Verification: `uv run pytest tests/commands/k8s/test_k8s_networking.py tests/commands/k8s/test_k8s_bootstrap.py`
- [x] 2.2 Move every test of `tests/commands/k8s/` that patches a `devops_cli` name to `process_fake`, `cluster`, `web`, `scanner_fake`, `keyring_store`, `clock`, `tcp_probe` or `config`, and keep its name
  - Verification: `uv run pytest tests/commands/k8s`
- [x] 2.3 Move the two tests of the forward daemon that read the source of `networking.py` or replaced its `subprocess` name to `process_fake`
  - Verification: `uv run pytest tests/k8s/test_k8s_port_forward_daemon.py`
- [x] 2.4 Add the invariant test that holds `tests/commands/k8s/` to no string patch of a `devops_cli` name
  - Verification: `uv run pytest tests/invariants/test_source_tree.py`

## 3. Documents (documents)

- [x] 3.1 Name the `tcp_probe` fixture, the forward of `devops k8s port-forward` and the invariant test in `docs/TESTING.md`
  - Verification: `uv run devops ci docs`
- [x] 3.2 Check that the change folders are valid
  - Verification: `uv run devops openspec check`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 4086-k8s-command-tests-on-edge-fakes`
