# Proposal

## Why

The devcontainer has a limit of 2048 processes and threads, the default of rootless Podman. A burst of VS Code file searches fills it. Then the tools of agent sessions fail with exit code 1 or `can't start new thread`, and the sessions lose work. This happened on 2026-11-05 and on 2026-11-06 (#3722).

## What Changes

- `.devcontainer/devcontainer.json` adds `--pids-limit=8192` to `runArgs`, and keeps `--gpus all`.
- `tests/invariants/test_devcontainer_config.py` fails when `runArgs` holds no `--pids-limit`, or a value under 4096.
- `CONTRIBUTING.md` states the new limit, the cause of the bursts, and that the limit takes effect only after a person rebuilds the container.
- The file holds no comment about the measure: `tests/ai/benchmark/test_k8s_llm_gateway.py` and `tests/invariants/test_devcontainer_config.py` read it with `json.loads`, which refuses comments. `CONTRIBUTING.md` holds the measure instead.
- The change carries a spec delta because the container limit is a runtime setting that a person observes: the new capability `devcontainer-process-limit`. The document change in `CONTRIBUTING.md` has no scenario, because no test reads prose.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `devcontainer-process-limit`: The devcontainer raises the process limit of the container above the 2048 default, and a test guards the value.

### Modified Capabilities

None.

## Impact

- Configuration: `.devcontainer/devcontainer.json`
- Tests: `tests/invariants/test_devcontainer_config.py`
- Documents: `CONTRIBUTING.md`

## Feasibility

- Issue comments of 2026-11-06 name the cause: `ms-python.vscode-python-envs` 1.42.0 starts one `rg --files` scan for each created or deleted file, and each `rg` starts one thread for each of the 16 CPUs. The extension has no setting that turns this off (upstream microsoft/vscode-python-environments#1989). So the limit of the container is the fix that this repository owns.
- `/sys/fs/cgroup/pids.max` of the running container shows the 2048 limit, and the logger `pids.current` of 2026-11-05 and 2026-11-06 shows the bursts to 2048.
- Podman (`podman run --pids-limit`) and Docker (`docker run --pids-limit`) both accept the option, and `devcontainer.json` passes `runArgs` to the container engine as given. The limit applies only to a container that a person creates again, so the change cannot be proved in the running container. The test proves the configuration, and a person rebuilds the container.
- `.devcontainer/image/devcontainer.json` holds no `runArgs` and builds no container for this workspace, and `.devcontainer/Dockerfile` names no limit, so only the workspace file changes.
- `src/devops_cli/templates/devcontainer.json.j2` scaffolds the files of other repositories and stays as it is, because the issue concerns this container.

## Existing Tool Considered

`--pids-limit` is the standard option of `podman run` and `docker run`. The change builds no code of its own, and deletes no internal code. The cost is one run argument, one test and one paragraph.
