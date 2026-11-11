# Tasks

## 1. Read a YAML 1.1 boolean as the mode it names

Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/round_trip.py`, `tests/config/test_loki_url.py`, `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`, `tests/ai/ast/test_ai_ast_cli.py`. Changes: `src/devops_cli/config/defaults.py`, `tests/config/test_mode_yaml_booleans.py` (new), `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py`.

- [ ] 1.1 Write `tests/config/test_mode_yaml_booleans.py` with `test_a_bare_off_in_the_config_file_loads_as_the_mode_off`, `test_a_bare_on_in_the_config_file_loads_as_the_mode_on`, `test_the_decision_mode_reads_the_yaml_booleans` through `TypeAdapter(DecisionMode)`, `test_the_written_mode_reloads` through `RoadmapIntakeConfig`, and `test_config_set_writes_off_and_the_settings_load_it`; each fails before the change
  - Verification: `$ uv run devops ci test tests/config/test_mode_yaml_booleans.py tests/roadmap/intake/test_roadmap_intake_jev_shadow.py tests/commands/test_cli_startup_imports.py` fails on the base
- [ ] 1.2 Add `_read_yaml_bool_mode` and a private annotated mode type to `src/devops_cli/config/defaults.py`, and give `JevMode` and `DecisionMode` that type: `False` returns `off`, `True` returns `on`, and every other value passes through to the `Literal`. Replace `test_the_setting_is_off_by_default_and_refuses_the_old_bool` in `tests/roadmap/intake/test_roadmap_intake_jev_shadow.py` with `test_the_setting_is_off_by_default_and_reads_a_bare_on`, which asserts the default `off`, that `RoadmapIntakeConfig(jev=True).jev` is `on`, and that an unknown string still raises `ValidationError` at `jev`
  - Verification: `$ uv run devops ci test tests/config/test_mode_yaml_booleans.py tests/roadmap/intake/test_roadmap_intake_jev_shadow.py tests/commands/test_cli_startup_imports.py` passes

## 2. State the bare mode values on the intake page

Reads: `docs/roadmap/intake.md`. Changes: `docs/roadmap/intake.md`.

- [ ] 2.1 Add one sentence to the `Jev for the proposal` section of `docs/roadmap/intake.md`: a config file can give `roadmap.intake.jev` a bare `off` or `on`, because PyYAML reads a bare `off` as `false` and a bare `on` as `true`, and the settings read each as the mode it names
  - Verification: `$ uv run devops ci docs` passes
- [ ] 2.2 Edit `docs/roadmap/intake.md` with the sentence that the setting takes a bare `off` and `on`
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
