# Tasks

## 1. Read the version the command on PATH prints

Kind: behavior. Reads: `src/devops_cli/core/process.py`, `src/devops_cli/tools_lock/__init__.py`, `tests/tools_lock/test_tools_lock.py`. Changes: `src/devops_cli/tools_lock/versions.py` (new), `tests/tools_lock/test_versions.py` (new).

- [ ] 1.1 `tests/tools_lock/test_versions.py::test_path_version_reads_the_command_on_path` fails until the helper exists
  - Verification: `$ uv run devops ci test tests/tools_lock/test_versions.py` fails on the base
- [ ] 1.2 Add `version_line(output)` and `path_version(command)` to the new `src/devops_cli/tools_lock/versions.py`. `version_line` answers the first non-empty line of the output, stripped, or `None`. `path_version` resolves `command` with `shutil.which(command)`, with no path argument, so it reads the binary that the process PATH names; it answers `None` when PATH resolves nothing, else the path and the version line of `run_subprocess([path, "--version"], local_read=True)` when that run exits 0, and `None` for the version when it does not. Write the failing tests first: the line of a run, no command on PATH, a run that exits 1, and an output whose first lines are empty
  - Verification: `$ uv run devops ci test tests/tools_lock/test_versions.py` passes

## 2. Judge the check and only-missing by the version on PATH

Kind: behavior. Reads: `src/devops_cli/commands/install_tools.py`, `src/devops_cli/tools_lock/versions.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_install_tools.py`, `tests/support/tools.py`. Changes: `src/devops_cli/commands/install_tools.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_install_tools.py`.

- [ ] 2.1 `tests/commands/test_install_tools.py::test_check_prints_the_version_and_the_path_of_the_locked_command` fails until the check prints the version on the passing path
  - Verification: `$ uv run devops ci test tests/commands/test_install_tools.py` fails on the base
- [ ] 2.2 Add `check_version_differs`, `check_version_unreadable` and `check_version_at_pin` to the `InstallMessages` dataclass. Import `BIN_OPENSPEC` into `src/devops_cli/commands/install_tools.py` beside `BIN_NPM`. Add `_version_state(name, entry)`, which answers `path_version(BIN_OPENSPEC)` for the `openspec` tool and `None` for any other tool. Add `_version_problem(name, entry, state)`: the `check_version_differs` line when the state holds a version other than the lock's, the `check_version_unreadable` line when the state holds a path and no version, and `None` when PATH resolves no command or the version matches. Add `_version_line(name, entry, state)`, which answers `check_version_at_pin` with the name, the locked version and the path when the version matches. Replace the body of `_check_pins` with one that prints each problem of `_problems(targets, target_dir)` — the version problem of a tool first, the `check_off_pin` line only when there is none — raises `typer.Exit(1)` when there is a problem, and otherwise prints each `_version_line` and then `check_all_pinned`. Make `_off_pin` include a tool whose `_version_problem` is not `None`, so `--only-missing` installs it. Update the help of `--check` and `--only-missing` in `src/devops_cli/lang/en/help.py`. In `tests/commands/test_install_tools.py`, teach `_record_npm` to answer a `--version` run from a `version` argument that defaults to the lock's `openspec` version, before it reads `cwd` and `env`, and write the failing tests first: `test_check_prints_the_version_and_the_path_of_the_locked_command`, `test_check_fails_naming_the_version_the_binary_prints`, `test_check_fails_when_the_binary_prints_no_version` and `test_only_missing_installs_openspec_when_the_binary_on_path_prints_another_version`. Update `test_install_tools_installs_a_node_tool_and_check_finds_it_at_its_pin` to assert the version line
  - Verification: `$ uv run devops ci test tests/commands/test_install_tools.py` passes

## 3. Name the version the gate's binary prints

Kind: behavior. Reads: `src/devops_cli/openspec/gate.py`, `src/devops_cli/openspec/tool.py`, `src/devops_cli/tools_lock/__init__.py`, `src/devops_cli/tools_lock/versions.py`, `src/devops_cli/config/commands.py`, `src/devops_cli/lang/en/messages.py`, `tests/openspec/test_openspec_gate.py`, `tests/support/fakes/openspec.py`. Changes: `src/devops_cli/openspec/gate.py`, `src/devops_cli/lang/en/messages.py`, `tests/openspec/test_openspec_gate.py`, `tests/support/fakes/openspec.py`.

- [ ] 3.1 `tests/openspec/test_openspec_gate.py::test_the_gate_names_the_version_the_binary_prints` fails until the gate reads the version
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py` fails on the base
- [ ] 3.2 Add `VERSION_ARGS = ("--version",)` and `GateCheck.VERSION` to `src/devops_cli/openspec/gate.py`. Add `_version_finding(tool, root)`, which runs `tool.run(VERSION_ARGS, root)`, reads the first non-empty line with `version_line`, compares it with the `openspec` version of `load_tools_lock()`, and answers a finding for a mismatch or for a run that printed no line, naming `shutil.which(BIN_OPENSPEC)`, the printed version, the locked version and `MESSAGES.openspec.missing_hint`. `check_openspec` returns that one finding, before the other checks, when it is not `None`. Add `_planned(VERSION_ARGS, CHECKOUT_PLACEHOLDER)` to `plan_check` after the settings runs. Add `version_differs` and `version_unreadable` to the `OpenSpecMessages` dataclass. In `tests/support/fakes/openspec.py`, answer `("--version",)` from `self.version`, and add `("--version",)` to `EMPTY_TREE_COMMANDS` in `tests/openspec/test_openspec_gate.py`. Write the failing tests first: a mismatch names both versions and the install command with no `regenerate` and no `update --force` run, and the locked version keeps the skill finding
  - Verification: `$ uv run devops ci test tests/openspec/test_openspec_gate.py` passes

## 4. Describe the version read in the documents

Kind: other. Reads: `src/devops_cli/lang/en/help.py`, `docs/SDLC.md`, `README.md`, `docs/commands/install-tools.md`. Changes: `docs/commands/install-tools.md`, `docs/SDLC.md`, `README.md`.

- [ ] 4.1 Run `uv run devops docs generate` to rewrite `docs/commands/install-tools.md` from the new help of `--check` and `--only-missing`. Add the version read and the passing version line to the `openspec` row of `docs/SDLC.md` and to the `install-tools --check` sentence of `README.md`
  - Verification: `$ uv run devops ci --only docs` passes
- [ ] 4.2 Edit `docs/commands/install-tools.md`, `docs/SDLC.md` and `README.md`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
