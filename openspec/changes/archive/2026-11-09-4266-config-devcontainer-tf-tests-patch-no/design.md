# Design

## Decisions

- **Configuration via `config` and `isolate_devops_cli_config`**: Rather than patching `load_settings` or `save_settings`, tests set configuration values via the standard `config` fixture and verify file modifications through `isolate_devops_cli_config`.
- **Subprocess calls via `process_fake`**: Invocations of external CLI tools (`devcontainer`, `tofu`, `terraform`, `k6`, `helm`, `kubectl`) are scripted through `ProcessFake` answers instead of monkeypatching `run_subprocess`.
- **Kubernetes cluster interactions via `FakeCluster`**: For `test_k8s_bootstrap_mattermost.py`, resource creations and checks use the `cluster` fixture (`FakeCluster`).
- **Filesystem isolation via `tmp_path`**: Workspace root paths and project directories use real temporary paths instead of monkeypatching `_PROJECT_ROOT`.
- **Stdlib edge patching**: Where an edge is an unseamed stdlib function (such as `shutil.which`), monkeypatching the stdlib module itself (`shutil`, not `devops_cli.commands...shutil`) is used in accordance with `docs/TESTING.md`.

## Rejected alternatives

- **Keep internal monkeypatches under a ceiling**: Rejected by ADR 0005 and #1336 rules; all internal patches must be eliminated in favor of edge doubles.
- **Mock at product boundaries**: Rejected because mocking internal helpers allows regressions in call-site wiring and interface changes to go unnoticed.
