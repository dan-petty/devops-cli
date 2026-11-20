# Design

## Decisions

- **Delete, do not migrate.** A reader whose value came only from a pin goes: the installer, its plan, its messages, the `osv-scanner` audit of the lock files, the reader of `tools.lock` in `devops research`, the vendored gh-dash schema and the pin-comparing tests.
- **PATH is the one place of a tool.** `require_binary` finds `ruff` and `semgrep`; `ansible_tool` asks `check_binary` first, because a missing `ansible-runner` is a row of the onboard report. A resolved link names the folder of the Ansible commands.
- **The ruff check resolves before the pool.** `run_group_analysis` resolves `ruff` when a model runs, so a `DependencyError` never becomes `model-call-error` inside a job. The hint names the Ruff install page; the devtools image holds no Ruff.
- **A recorded version or none.** The analysis, the knowledge base and the profile read the versions of the tool runs. A manual drifts only from a recorded version, so a review with no run lists no drift.
- **No `--version` in the record path.** The canary and the tool executor record the installed distribution, else `unknown`, with the binary digest. They do not start a tool outside its sandbox for a version.
- **An old plan record is planned again.** `PlanContent` refuses an unknown field, so a record with `ansible_core` does not read, and the apply says to plan again.
- **The CLIs of the alternatives inventory.** `config/commands.py` names each CLI that devops-cli starts. A CLI that only the image holds counts as in use only when a deployed path names it.
- **The image scan replaces the tag floor.** The third-party image scan runs one matrix job for each pinned cluster image.

## Rejected alternatives

- Keep `tools.lock` as the source of the versions: the owner decision of 2026-11-19 forbids a pin in `src/`.
- Move the pins into a generated file under `src/`: it is a pin that a dependency update must change.
- Keep `~/.local/bin` as a second search folder: PATH is the one source.
- Run `<tool> --version` for each recorded run: the floor of the test suite refuses it, and it starts the tool outside the sandbox.
