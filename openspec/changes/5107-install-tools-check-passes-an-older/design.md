# Design

## Decisions

- **Read the version from the command that the process PATH resolves, and never from the link in the target directory.**: `src/devops_cli/commands/install_tools.py:380:search_path = os.pathsep.join((str(target_dir), os.environ.get("PATH", "")))` puts the target directory first, so a link at the pin hides the older binary that the gate actually runs.
- **Compare the printed version with the lock as exact text.**: Both sides print three numeric parts, and `src/devops_cli/roadmap/runner_tools.py:def expected_text` already compares an `openspec --version` line with the lock, so a parse would add a failure mode with no gain.
- **Print `openspec <locked version>` with the path of the command on the passing path.**: The issue asks the check to name the version and the binary path when it passes, and a person then sees which binary the gate will run.
- **Read the version for the `openspec` entry of the lock only.**: Its version decides the committed skills under `.claude/skills/`; the other Node tool, `src/devops_cli/tools_lock/tools.lock:604:[npm.devcontainers-cli]`, writes no committed file, so it is allowlisted out of the guard.
- **When the command on PATH prints no version, the check fails instead of passing.**: A binary that cannot state its version cannot be shown to be the lock's, and the gate cannot be trusted with the text it writes.
- **When PATH resolves no command, the link check alone decides and no version line prints.**: `tests/commands/test_install_tools.py:660:def test_check_passes_only_when_every_tool_is_at_its_pin(` runs the check with a PATH that holds no tool, and the target directory is then what the check judges.
- **The version read passes `local_read=True`, so a dry run still reads it.**: `src/devops_cli/core/process.py:1153:def run_subprocess(` answers a planned result for a call that is not a local read, and `src/devops_cli/devcontainer/devcontainer_plans.py:def plan_install_tools` never calls `_off_pin`, so the read sends no request and keeps the check's dry-run class.
- **The gate reports one version finding and runs no other check when the versions differ.**: Every other answer comes from the same binary, so a check under the wrong binary judges text that binary did not write.
- **The gate runs the version through `OpenSpecTool.run`, so a dry run lists it.**: `src/devops_cli/openspec/gate.py:221:def plan_check() -> list[PlannedRequest]:` must list every command that the gate runs, and the fake already answers that seam.

## Rejected alternatives

- **Read the tools lock alone in the check.**: That is the defect: `src/devops_cli/commands/install_tools.py:376:def _installed(name: str, entry: LockedTool, target_dir: Path) -> str:` prints the lock's version beside a path and runs no binary, so an older binary on PATH passes.
- **Find the binary with `_installed`'s search order, target directory first.**: `src/devops_cli/commands/install_tools.py:380:search_path = os.pathsep.join((str(target_dir), os.environ.get("PATH", "")))` reads the target-directory link at the pin while an older binary earlier on PATH is the one that runs, which is the defect of the issue.
- **Keep the passing output as the summary line alone.**: The issue asks the passing check to print `openspec 1.17.0` with the binary path, and `src/devops_cli/commands/install_tools.py:428:print_success(MESSAGES.install.check_all_pinned.format(count=len(targets), path=target_dir))` names neither the version nor the binary that the gate runs.
- **Read the version of every Node tool of the lock.**: The other entry, `src/devops_cli/tools_lock/tools.lock:604:[npm.devcontainers-cli]`, writes no committed file, and the format of its `--version` output is unverified in this run, so a guard over it could fail a correct install.
- **Keep the skill advice and add a warning above it.**: The reader still follows the advice, and the older binary writes the older skill text over the committed text.
- **Detect the version from the committed `generatedBy` value of a skill.**: That value names the text that is committed and matches the lock, so it cannot show that the binary on PATH is older.
