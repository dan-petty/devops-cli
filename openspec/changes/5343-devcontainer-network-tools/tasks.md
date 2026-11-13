# Tasks

## 1. Install the network diagnostics tools in the image

Kind: behavior. Reads: `.devcontainer/Dockerfile`, `tests/invariants/test_devcontainer_config.py`. Changes: both.

- [x] 1.1 Add a test that reads the system-package step of the last stage and fails when a network diagnostics package is absent
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py`
- [x] 1.2 Add `iputils-ping`, `iputils-tracepath`, `traceroute`, `mtr-tiny`, `netcat-openbsd` and `tcpdump` to the step, and say in its comment how each tool gets its socket
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py`

## 2. Let the user vscode open an ICMP echo socket

Kind: behavior. Reads: `.devcontainer/devcontainer.json`, `src/devops_cli/templates/devcontainer.json.j2`, `tests/invariants/test_devcontainer_config.py`. Changes: all three.

- [x] 2.1 Add a test that fails when `runArgs` of the workspace has no `--sysctl=net.ipv4.ping_group_range=1000 1000`, or when the `runArgs` of a scaffolded devcontainer differ
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py`
- [x] 2.2 Add the run argument to `.devcontainer/devcontainer.json` and to `src/devops_cli/templates/devcontainer.json.j2`
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py tests/core/test_template_rendering.py tests/commands/test_devcontainer.py`

## 3. Document the tools and their limits

Kind: documents. Changes: `docs/DEVCONTAINER_USAGE.md`, `CONTRIBUTING.md`.

- [x] 3.1 List the network tools in `docs/DEVCONTAINER_USAGE.md` with the run argument, `sudo tcpdump` and the pasta limit, and name the run argument and the rebuild in `CONTRIBUTING.md`
  - Verification: `$ git grep -n "ping_group_range=1000 1000" docs/DEVCONTAINER_USAGE.md CONTRIBUTING.md`

## Workflow follow-up

- Pending a person: rebuild the devcontainer after the release publishes the image (`Dev Containers: Rebuild Container`). Then, as `vscode`, run `ping -c 1 example.com`, `tracepath -n example.com`, `mtr --report -c 1 example.com`, `nc -zv example.com 443` and `sudo tcpdump -c 1`. `cat /proc/sys/net/ipv4/ping_group_range` shows `1000 1000`.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
