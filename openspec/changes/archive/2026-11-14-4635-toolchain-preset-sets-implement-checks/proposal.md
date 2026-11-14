# Proposal: #4635

## Why
The implement job runs one fixed check set in every repository. A clone with no `sgconfig.yml` fails `constructs`, and a clone with no `openspec/config.yaml` fails `openspec`. Implement now runs in all seven repositories. Each target repository must supply its check set from its toolchain preset. Closes #4635.

## What Changes
- Replace `[implement.steps]` with `[project] toolchain = "neutral" | "devops-cli"` in `.devops/roadmap.toml`.
- Move `implement_steps.py` to `src/devops_cli/roadmap/project_profile.py` and implement `resolve_profile(source, ref) -> ProjectProfile`.
- Add `src/devops_cli/roadmap/toolchains.py` defining frozen dataclass presets `devops-cli` and `neutral`.
- Update `scoped_checks` to read `static_check` and `test_command` from the resolved profile preset.
- Run docs and archive steps only when declared by the profile and enabled by `uses_openspec`.
- Gate `ruff format`, `ruff check` and `mypy` in step execution behind `step_gates = "ruff-mypy"`.

## Capabilities
- Read project profiles from `.devops/roadmap.toml` at `origin/<default>`.
- Support `devops-cli` and `neutral` toolchain presets.
- Gate static checks, tests, docs, archive, and formatting/typing by toolchain preset.

## Impact
- Enables the implement job to run safely across diverse repositories without failing on missing tool configurations.
- Removes obsolete `[implement.steps]` configuration.

## Feasibility
The trusted read pattern from `implement_steps.py` and `uses_openspec` (#4629) is already proven in production.

## Existing Tool Considered
No open tool maps a repository to a check set. pre-commit runs target-specific hooks, and CI verifies pull requests. The preset is typed internal data.
