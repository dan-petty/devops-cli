# Task: The Devcontainer Post-Create and Post-Start Tests Start No Real Installer, uv Sync, kubectl or sudo (#1731)

**Issue**: [#1731](https://github.com/dan-petty/devops-cli/issues/1731)
**Scope**: scope/ci
**Feasibility**:
- A Popen recorder over the tests, with `claude` taken off PATH as on the GitHub runner, showed what they start:
  - Claude Code's real installer, `curl -fsSL https://claude.ai/install.sh | bash`, a 276 MB download in each of four post-create tests.
  - `uv venv` and `uv pip sync` of semgrep and bandit in the instruction-generator test.
  - `kubectl config get-contexts -o name` in four post-start tests.
  - `sudo chown -R None:1000` in the ownership test.
- The kubectl call happens because an unset `k8s.context` defaults to `minikube` (`src/devops_cli/config/settings.py`). The test floor's config isolation holds, and nothing comes from a person's own configuration.

## Description

The tests double the programs post-create looks for and name no Kubernetes context. The ownership test removes `os.getuid` rather than making it return `None`. Every assertion is kept, no test is added, and product code is unchanged.

- [x] An `image_programs_installed` fixture doubles `shutil.which` and answers every program as installed, as in the published image. Three `TestDevcontainerCli` tests take it: post_create, setup_volume and run_lifecycle. The instruction-generator test applies the same double and passes `--skip-tools`.
- [x] A `no_configured_k8s_context` fixture writes `k8s.context: ""` into the test's own config, so post-start leaves kubectl alone in its four tests.
- [x] `test_ensure_path_ownership_and_mount_edge_cases` tests a missing `getuid` by deleting it inside `monkeypatch.context()`, so `_ensure_path_ownership` returns before any `sudo chown`.
- [x] Measured on a runner-like PATH: post_create went from 19.4s to 0.03s, and the instruction-generator test from 24.0s to 0.09s. On the runner, about 55s of summed test time (16.9 + 13.0 + 12.8 + 12.0s) and about 1.1 GB of downloads per CI run go away.
- Found here and filed separately:
  - #1728: post-create reports a failed installer download as installed.
  - #1729: the `DEVOPS_CLI_SKIP_TOOL_BOOTSTRAP` test switch in product code.
