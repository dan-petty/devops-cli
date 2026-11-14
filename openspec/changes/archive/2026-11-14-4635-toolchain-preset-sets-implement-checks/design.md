# Design

## Decisions
1. **Toolchain presets module**:
   Define `ToolchainPreset` and presets `devops-cli` and `neutral` in `src/devops_cli/roadmap/toolchains.py`.
   - `devops-cli`: static check `uv run devops ci --check --only constructs,docs,openspec`, test command `("uv", "run", "devops", "ci", "test", "{tests}")`, docs step enabled, archive argv `("uv", "run", "devops", "openspec", "archive", "<change>")`, step_gates "ruff-mypy".
   - `neutral`: no static check, no test command, no docs step, archive argv `("openspec", "archive", "<change>", "--yes")`, no step gates.

2. **Project Profile**:
   Define `ProjectProfile` in `src/devops_cli/roadmap/project_profile.py`.
   Read `[project] toolchain` from `.devops/roadmap.toml` at `origin/<default>`.
   Default to `neutral` when `.devops/roadmap.toml` is missing.
   Raise `ConfigurationError` when the toolchain is unknown.

3. **Step Gates & Scoped Checks**:
   `scoped_checks` uses preset's static check and test command.
   `_format_failure` and `_static_failure` only run if `step_gates == "ruff-mypy"`.

## Rejected Alternatives
- Keep `[implement.steps]` as a shim: Rejected. The project is pre-1.0 and does not write legacy shims.
- Guess test commands from lockfiles: Rejected. Unreliable and adds maintenance overhead.
