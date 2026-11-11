# Design

## Decisions
- `POINT_CUTS` in `devops_cli.roadmap.decision_table` maps each point name to its cuts file. The paths are from the folder of the module, as `CUTS_FILE` of `stage_jev_screen` is from its own folder, so the two paths are equal in a checkout and in an installed package.
- `check_modes(modes, cuts=POINT_CUTS)` holds the one copy of the check. It takes the table as an argument, so a test gives it a table under `tmp_path`.
- The validator imports `decision_table` in the function, when a key is set. A config with no key imports no module more than before.
- The probe of the `startup-imports` row writes a config file and sets `DEVOPS_CLI_CONFIG`, as the runner Jobs do with `/config/devops-cli.yaml`. It also prints the loaded modes, so a probe whose settings do not hold the key cannot pass.

## Rejected alternatives
- Import `pydantic_ai.models.decision` only when a point asks the model, in `decision_point.py` and `stage_jev_screen.py`. The settings then still import every point module, its fit and telemetry modules, and each point module must stay free of an eager import of pydantic_ai. One new point with a module-level import brings the cost back.
- A table of names only. It loses the refusal of `on` for a point with no cuts file, which the settings have today (`decision-workflows`, "The mode of each point is a setting").
- A lazy `REGISTRY` through a module `__getattr__` in `decision_registry`. It hides the import in an attribute read, and the type of `REGISTRY` then needs a `TYPE_CHECKING` copy.
