# Proposal

## Why

The check trusts the tools lock and the link in the target directory, so a devcontainer image with an older `openspec` binary passes it (#5107). The gate then judges the committed skills with that binary and advises `regenerate`, which writes the older skill text over the committed text. The change makes the check and the gate read the version that the binary on PATH prints.

## What Changes

- `devops install-tools --check` runs the `openspec` command that PATH resolves with `--version`, and fails naming the path, the printed version and the locked version when they differ.
- `devops install-tools --check` fails naming the path when the `openspec` command on PATH prints no version.
- `devops install-tools --check` prints `openspec 1.17.0` with the path of the command and exits 0 when the command on PATH prints the locked version.
- `devops install-tools --check` keeps the link check when PATH resolves no `openspec` command, so a target directory that is not on PATH is still judged by its links.
- `devops install-tools --only-missing` installs the locked `openspec` when the command on PATH prints another version.
- `devops openspec check` runs `openspec --version` before its other checks and reports one problem naming the printed version, the locked version, the binary path and `uv run devops install-tools --tool openspec --only-missing`.
- The OpenSpec gate reports no skill finding and advises no `regenerate` when the binary on PATH differs from the lock.
- A new `src/devops_cli/tools_lock/versions.py` holds `version_line`, the first non-empty line of an output, and `path_version`, the version of the command that PATH resolves.
- `docs/commands/install-tools.md` is regenerated from the new help text, and `docs/SDLC.md` and `README.md` describe the version read.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `tools-lock-install`: The check reads the version the openspec command prints, Only-missing installs openspec when PATH holds another version

### Modified Capabilities

- `openspec-check`: The gate reads the version of the command on PATH

## Impact

- Code: `src/devops_cli/tools_lock/versions.py`, `src/devops_cli/commands/install_tools.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/openspec/gate.py`
- Documents: `docs/commands/install-tools.md`, `docs/SDLC.md`, `README.md`
- Tests: `tests/tools_lock/test_versions.py`, `tests/commands/test_install_tools.py`, `tests/openspec/test_openspec_gate.py`, `tests/support/fakes/openspec.py`

## Feasibility

- The cited paths exist at the staging commit: the probes say "The path `src/devops_cli/tools_lock/openspec/package.json` is a file of the staging commit." and the same for `src/devops_cli/commands/openspec.py`, `src/devops_cli/lang/en/messages.py` and `tests/commands/test_install_tools.py`.
- `read_file` of `src/devops_cli/commands/install_tools.py` lines 320 to 500 showed the defect: `src/devops_cli/commands/install_tools.py:363:def _at_pin(name: str, entry: LockedTool, target_dir: Path) -> bool:` judges a tool by the link in the target directory, and `src/devops_cli/commands/install_tools.py:376:def _installed(name: str, entry: LockedTool, target_dir: Path) -> str:` prints the lock's version with a path. No line runs the binary.
- The review finding on the resolution is right, and the plan follows it: `src/devops_cli/commands/install_tools.py:380:search_path = os.pathsep.join((str(target_dir), os.environ.get("PATH", "")))` puts the target directory before PATH, so a link at the pin hides an older binary earlier on PATH. The new `path_version` calls `shutil.which(command)` with no `path` argument, so it reads the binary that the process PATH names.
- The review finding on the passing criterion is right, and the plan corrects it: the passing path printed only `src/devops_cli/commands/install_tools.py:428:print_success(MESSAGES.install.check_all_pinned.format(count=len(targets), path=target_dir))`, and the one line that names a version and a path is the failing line `src/devops_cli/lang/en/messages.py:417:check_off_pin: str = "{name} {version}: {installed}"`. Group 2 now prints `openspec <locked version>` with the path of the command on the passing path, and its test asserts that line.
- The review finding on the count is right, and the plan corrects it: `list_files` of `src/devops_cli/tools_lock` showed the directories `devcontainers-cli`, `openspec` and `style-dictionary`, but the lock holds two Node tools, `src/devops_cli/tools_lock/tools.lock:598:[npm.openspec]` and `src/devops_cli/tools_lock/tools.lock:604:[npm.devcontainers-cli]`. `style-dictionary` is no entry of the lock, as `tests/tools_lock/test_tools_lock.py:311:assert (npm_rules, "style-dictionary" in load_tools_lock().npm) == ([], False)` asserts. The set is those two entries: `openspec` is guarded, and `devcontainer` is allowlisted with the reason in the decisions.
- The lock's pin and the command the check reads: `src/devops_cli/tools_lock/tools.lock:599:version = "1.17.0"` and `src/devops_cli/tools_lock/tools.lock:602:bin = "openspec"` give the tool and its version, and `src/devops_cli/config/commands.py:38:BIN_OPENSPEC: str = "openspec"` names the command that the guard reads.
- The read of the version is the rule the image already applies: `src/devops_cli/roadmap/runner_tools.py:131:_locked("openspec", "ci:openspec", "hook:openspec-gate"),` builds the check `("openspec", "--version")` through `src/devops_cli/roadmap/runner_tools.py:def _locked`, and `src/devops_cli/roadmap/runner_tools.py:def expected_text` compares its output with `src/devops_cli/tools_lock/__init__.py:def load_tools_lock`. So the binary prints its version on one line and the lock is the text to compare.
- The premise is confirmed and the staged value is quoted: the issue's `openspec --version` prints `1.14.3`, and the lock at `src/devops_cli/tools_lock/tools.lock:599:version = "1.17.0"` pins 1.17.0, so an exact compare of the printed line fails on that host. The binary's version in a devcontainer image is `not checked`: no tool of this run ran a program.
- The gate half: `src/devops_cli/openspec/gate.py:189:def check_openspec(root: Path) -> list[GateFinding]:` runs the checks, `src/devops_cli/openspec/gate.py:221:def plan_check() -> list[PlannedRequest]:` lists them for a dry run, and `src/devops_cli/lang/en/messages.py:484:skill_differs: str = (` carries the `regenerate` advice. `src/devops_cli/openspec/tool.py:66:def run(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:` starts the binary, so the version run joins the plan.
- The version run is a local read: `src/devops_cli/core/process.py:1153:def run_subprocess(` returns a `PlannedProcessResult` in a dry run for a call that is not `local_read`, so `path_version` passes `local_read=True` and the check reads the binary in a dry run too. The npm double of `tests/commands/test_install_tools.py` stands in at `subprocess.run`, which `run_subprocess` starts, so a `--version` run reaches it.
- The tests that judge this output today are `tests/commands/test_install_tools.py:660:def test_check_passes_only_when_every_tool_is_at_its_pin(`, which sets `tests/commands/test_install_tools.py:665:monkeypatch.setenv("PATH", str(tmp_path / "empty"))` and so resolves no command, and `tests/openspec/test_openspec_gate.py:90:def test_the_plan_is_the_commands_the_gate_runs(openspec_fake: OpenSpecFake) -> None:`, whose list is the constant `tests/openspec/test_openspec_gate.py:26:EMPTY_TREE_COMMANDS = [`.
- The fake answers the locked version: `tests/fixtures/openspec_runs/recorded_runs.json:511:"version": "1.17.0"` is what `openspec_fake` holds, so answering `--version` from it keeps every existing gate test green.
- No function the plan calls needs a checkout, a client or a network. `path_version` and `OpenSpecTool.run` need the `openspec` program on PATH, and the tests answer it from `tests/support/fakes/openspec.py:180:def run(self, args: Any, *popenargs: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:` and from the `run` double of `tests/commands/test_install_tools.py`.
- Runner capabilities: the verify programs are `uv` and `devops`, both in the runner image's tool list, and `openspec` is a runner tool too. `npm` is `NOT_IN_RUNNER`, and no test of this plan starts it: the Node install is doubled. The failure classes the plan can raise are `test` and `lint`. The tests write only under the pytest temporary directory, so `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault` hold.
- First checks against the real system: on a host whose `openspec` prints a version other than the lock's, `uv run devops install-tools --check --tool openspec` must exit 1 and print the path and both versions, and `uv run devops ci --only openspec` must report the version problem with no skill advice. On a host at the lock, `uv run devops install-tools --check --tool openspec` must exit 0, print `openspec 1.17.0` with the path, and `uv run devops ci --only openspec` must keep the skill check.

## Existing Tool Considered

No open, maintained tool reads the version of an npm-installed CLI on PATH and compares it with a project lock; a package manager reports only what it installed. The change reuses `run_subprocess` with `local_read`, the lock reader and the message table, and adds about 30 lines of its own: 6k tokens to build, 1k tokens a year to keep and fix, and half a day elapsed.

## Dependencies

None.
